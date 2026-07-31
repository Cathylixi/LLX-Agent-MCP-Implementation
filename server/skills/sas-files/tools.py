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
    """List the raw SAS clinical trial domain datasets (.sas7bdat files) available in cloud storage.

    Use this to discover what SAS domain files exist (e.g. dm, ae, cm, vs).
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
    """Get a temporary (1-hour) direct download link for one SAS dataset file.

    filename must exactly match a name returned by list_sas_files (e.g. "dm.sas7bdat").
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
