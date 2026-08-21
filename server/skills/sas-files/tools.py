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
def describe_sas_file(filename: str, rows: int = 20, start_row: int = 0) -> dict:
    """Get the full structure of a SAS dataset PLUS a page of its actual row data.

    Use this for ANY request to see what's INSIDE a SAS file — variable
    names, labels, types, total row/column counts, and real data values
    (e.g. "what columns does dm have", "what's dm's data dictionary", "show
    me some ae rows", "how many rows does adae have").

    - `variables`, `row_count`, and `column_count` describe the ENTIRE file —
      these are never truncated, since metadata is cheap to read regardless
      of file size.
    - Actual row data IS bounded per call (`rows`, default 20, max 500) —
      one response cannot hold an entire large dataset (message-size limits).
      To see more of the data, call again with `start_row` advanced by
      however many rows you've already seen (e.g. start_row=500 for the next
      batch) and keep going until you've covered `row_count` rows total.

    filename must exactly match a name returned by list_sas_files. The file
    is read on the server — it never has to be downloaded locally.
    """
    print(
        f"[SKILL CALLED] describe_sas_file({filename!r}, rows={rows!r}, start_row={start_row!r})",
        flush=True,
    )

    rows = max(1, min(rows, 500))  # keep the row-data part of the response bounded
    start_row = max(0, start_row)

    container, error = _get_container_client()
    if error:
        return {"error": error}

    try:
        import io

        import pandas as pd

        blob_client = container.get_blob_client(filename)
        raw = blob_client.download_blob().readall()

        # A single chunksize read gets us both: the reader's header metadata
        # (row_count/column_count/column_labels, parsed up front regardless
        # of chunksize) and, from the chunk itself, real dtypes + the row
        # window we need. sas7bdat isn't randomly seekable, so reaching
        # start_row still means reading (and discarding) everything before it.
        reader = pd.read_sas(io.BytesIO(raw), format="sas7bdat", chunksize=start_row + rows)
        chunk = next(reader, None)

        total_rows = getattr(reader, "row_count", None)
        total_columns = getattr(reader, "column_count", None)
        labels = getattr(reader, "column_labels", None) or []

        if chunk is None:
            columns, variables, page = [], [], []
        else:
            columns = [str(c) for c in chunk.columns]
            variables = [
                {
                    "name": name,
                    "label": (labels[i].strip() if i < len(labels) and labels[i] else None),
                    "type": str(chunk[name].dtype),
                }
                for i, name in enumerate(columns)
            ]
            page_df = chunk.iloc[start_row : start_row + rows]
            page = [
                {str(col): _json_safe(v) for col, v in row.items()}
                for row in page_df.to_dict(orient="records")
            ]

        return {
            "filename": filename,
            "row_count": total_rows,
            "column_count": total_columns if total_columns is not None else len(columns),
            "variables": variables,
            "start_row": start_row,
            "rows_returned": len(page),
            "rows": page,
        }
    except Exception as e:
        return {"error": f"Could not read {filename!r}: {e}"}


@mcp.tool()
def read_pdf_text(filename: str, pages: str = None) -> dict:
    """Read a PDF's text WITH each text block's position on the page (x0,y0,x1,y1 in points).

    Use this for any request to read/see what's inside a PDF (e.g. "acrf.pdf")
    — this is a document, not a SAS dataset, so describe_sas_file won't work
    on it. Positions matter for documents like an annotated CRF (aCRF), where
    an SDTM domain/variable annotation is printed physically NEAR the field it
    applies to but is not necessarily adjacent to it in plain reading order —
    use each block's bbox to judge which annotation belongs to which field by
    proximity (e.g. same page, closest y, or aligned x), don't assume the
    block that happens to come right after a question in the list is its
    annotation.

    By default reads every page. If too large for one response, pass `pages`
    as a 1-indexed range like "1-20" to read just that slice, then call again
    with the next range (check `total_pages` to know when to stop).
    filename must exactly match a name returned by list_sas_files.
    """
    print(f"[SKILL CALLED] read_pdf_text({filename!r}, pages={pages!r})", flush=True)

    container, error = _get_container_client()
    if error:
        return {"error": error}

    try:
        import io

        import fitz  # PyMuPDF

        blob_client = container.get_blob_client(filename)
        raw = blob_client.download_blob().readall()

        doc = fitz.open(stream=raw, filetype="pdf")
        total_pages = doc.page_count

        start, end = 0, total_pages
        if pages:
            bounds = pages.split("-")
            start = max(0, int(bounds[0]) - 1)
            end = min(total_pages, int(bounds[1]) if len(bounds) > 1 else start + 1)

        pages_out = []
        for i in range(start, end):
            blocks = doc[i].get_text("blocks")  # (x0, y0, x1, y1, text, block_no, block_type)
            pages_out.append(
                {
                    "page": i + 1,
                    "blocks": [
                        {
                            "bbox": [round(b[0], 1), round(b[1], 1), round(b[2], 1), round(b[3], 1)],
                            "text": b[4].strip(),
                        }
                        for b in blocks
                        if b[4].strip()
                    ],
                }
            )
        doc.close()

        return {
            "filename": filename,
            "total_pages": total_pages,
            "pages_returned": f"{start + 1}-{end}",
            "pages": pages_out,
        }
    except Exception as e:
        return {"error": f"Could not read {filename!r}: {e}"}
