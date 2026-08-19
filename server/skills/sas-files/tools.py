"""Code tools for the `sas-files` skill — run on the server (storage key stays secret)."""

import os
from datetime import datetime, timedelta, timezone

from app import mcp

CONTAINER_NAME = "sas-datasets"


def _get_container_client():
    """Return (container_client, error). Only this skill needs azure-storage-blob."""
    conn_str = os.environ.get("SAS_STORAGE_CONNECTION_STRING")
    if not conn_str:
        return None, "Storage is not configured on the server (SAS_STORAGE_CONNECTION_STRING missing)."

    from azure.storage.blob import BlobServiceClient

    service = BlobServiceClient.from_connection_string(conn_str)
    return service.get_container_client(CONTAINER_NAME), None


@mcp.tool()
def list_sas_files() -> dict:
    """List ALL company files in cloud storage: SAS datasets (.sas7bdat) AND documents like CRFs (.pdf).

    Use this for ANY request about SAS files, SAS datasets, domain files
    (e.g. dm, ae, cm, vs, lb, mh, ex), CRFs, or study documents. Files are
    organized by study in subfolders (e.g. "SPI-611/dm.sas7bdat"). This data
    lives ONLY in Azure Blob Storage, never on the local machine — call this
    tool instead of searching local folders, even if none are found there.
    """
    print("[SKILL CALLED] list_sas_files()", flush=True)

    container, error = _get_container_client()
    if error:
        return {"error": error}

    try:
        files = [{"name": b.name, "size_bytes": b.size} for b in container.list_blobs()]
        return {"container": CONTAINER_NAME, "files": files, "count": len(files)}
    except Exception as e:
        return {"error": f"Could not list files: {e}"}


@mcp.tool()
def get_sas_file_download_url(filename: str) -> dict:
    """Get a temporary (1-hour) direct download link for one file (SAS dataset, CRF PDF, etc).

    filename must exactly match a name returned by list_sas_files (e.g. "dm.sas7bdat" or "SPI-611/acrf.pdf").
    This file is NOT on the local machine — this is the only way to fetch it.
    """
    print(f"[SKILL CALLED] get_sas_file_download_url({filename!r})", flush=True)

    container, error = _get_container_client()
    if error:
        return {"error": error}

    try:
        from azure.storage.blob import BlobSasPermissions, generate_blob_sas

        sas_token = generate_blob_sas(
            account_name=container.account_name,
            container_name=CONTAINER_NAME,
            blob_name=filename,
            account_key=container.credential.account_key,
            permission=BlobSasPermissions(read=True),
            expiry=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        blob_client = container.get_blob_client(filename)
        return {
            "filename": filename,
            "download_url": f"{blob_client.url}?{sas_token}",
            "expires_in": "1 hour",
        }
    except Exception as e:
        return {"error": f"Could not generate download link for {filename!r}: {e}"}


def _json_safe(value):
    """Convert one pandas/numpy cell value into something JSON-serializable."""
    import math

    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if hasattr(value, "isoformat"):  # datetime / Timestamp
        return value.isoformat()
    if isinstance(value, float) and math.isnan(value):
        return None
    return value


@mcp.tool()
def preview_sas_file(filename: str, rows: int = 20) -> dict:
    """Read the actual contents of a SAS data file: its column names and the first N rows.

    Use this whenever the user wants to see what's INSIDE a SAS file (not just
    its name/size) — e.g. "what columns does dm have", "show me some ae rows".
    filename must exactly match a name returned by list_sas_files. The file is
    read on the server and only the requested rows are returned — the full
    file never has to be downloaded locally.
    """
    print(f"[SKILL CALLED] preview_sas_file({filename!r}, rows={rows!r})", flush=True)

    rows = max(1, min(rows, 500))  # keep responses (and server memory) bounded

    container, error = _get_container_client()
    if error:
        return {"error": error}

    try:
        import io

        import pandas as pd

        blob_client = container.get_blob_client(filename)
        raw = blob_client.download_blob().readall()

        # chunksize makes pandas parse incrementally instead of loading every
        # row into memory before we only keep the first `rows` of them.
        reader = pd.read_sas(io.BytesIO(raw), format="sas7bdat", chunksize=rows)
        chunk = next(reader)

        records = [
            {str(col): _json_safe(v) for col, v in row.items()}
            for row in chunk.to_dict(orient="records")
        ]
        return {
            "filename": filename,
            "columns": [str(c) for c in chunk.columns],
            "rows_returned": len(records),
            "rows": records,
        }
    except Exception as e:
        return {"error": f"Could not read {filename!r}: {e}"}


@mcp.tool()
def read_pdf_text(filename: str, pages: str = None) -> dict:
    """Read the full text content of a PDF document in cloud storage (e.g. a CRF).

    Use this for any request to read/see what's inside a PDF (e.g. "acrf.pdf")
    — this is a document, not a SAS dataset, so preview_sas_file won't work on
    it. By default this returns text from EVERY page. If the document turns
    out to be too large for one response, pass `pages` as a 1-indexed range
    like "1-20" to read just that slice, then call again with the next range
    (check `total_pages` in the response to know when to stop).
    filename must exactly match a name returned by list_sas_files.
    """
    print(f"[SKILL CALLED] read_pdf_text({filename!r}, pages={pages!r})", flush=True)

    container, error = _get_container_client()
    if error:
        return {"error": error}

    try:
        import io

        from pypdf import PdfReader

        blob_client = container.get_blob_client(filename)
        raw = blob_client.download_blob().readall()

        reader = PdfReader(io.BytesIO(raw))
        total_pages = len(reader.pages)

        start, end = 0, total_pages
        if pages:
            bounds = pages.split("-")
            start = max(0, int(bounds[0]) - 1)
            end = min(total_pages, int(bounds[1]) if len(bounds) > 1 else start + 1)

        page_texts = [reader.pages[i].extract_text() or "" for i in range(start, end)]

        return {
            "filename": filename,
            "total_pages": total_pages,
            "pages_returned": f"{start + 1}-{end}",
            "text": "\n\n".join(page_texts),
        }
    except Exception as e:
        return {"error": f"Could not read {filename!r}: {e}"}
