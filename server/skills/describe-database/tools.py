"""Code tools for the `database` skill — run on the server (DB key stays secret)."""

import json
import os
import re
from datetime import date, datetime

from app import mcp

DATABASE_NAME = "llxdocument"
STUDIES_COLLECTION = "studies"
MAX_DOCUMENTS_TO_SCAN = 200
MAX_RETURNED_CONTENT_CHARS = 120_000


def _get_database():
    """Return (client, database, error) without exposing the connection string."""
    uri = os.environ.get("MONGO_URI")
    if not uri:
        return None, None, "Database is not configured on the server (MONGO_URI missing)."

    try:
        from pymongo import MongoClient

        client = MongoClient(uri, serverSelectionTimeoutMS=8000)
        return client, client[DATABASE_NAME], None
    except Exception as exc:
        return None, None, f"Could not connect to the database ({type(exc).__name__})."


def _collect_search_text(value, parts, max_parts=20_000):
    """Collect bounded field names and scalar values for schema-agnostic matching."""
    if len(parts) >= max_parts:
        return
    if isinstance(value, dict):
        for key, child in value.items():
            parts.append(str(key)[:500])
            _collect_search_text(child, parts, max_parts)
            if len(parts) >= max_parts:
                break
    elif isinstance(value, (list, tuple)):
        for child in value:
            _collect_search_text(child, parts, max_parts)
            if len(parts) >= max_parts:
                break
    elif value is not None:
        parts.append(str(value)[:4_000])


def _document_matches(document, study_number, document_type=None):
    parts = []
    _collect_search_text(document, parts)
    searchable = "\n".join(parts).casefold()
    study_match = study_number.casefold() in searchable
    type_match = not document_type or document_type.casefold() in searchable
    return study_match and type_match


def _json_safe(value):
    if isinstance(value, dict):
        return {str(key): _json_safe(child) for key, child in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(child) for child in value]
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _summarize_value(value, depth=0, max_depth=6, sample_items=3):
    """Describe nested storage while keeping the default response compact."""
    if depth >= max_depth:
        return {"type": type(value).__name__, "truncated_at_depth": max_depth}
    if isinstance(value, dict):
        return {
            "type": "object",
            "field_count": len(value),
            "fields": {
                str(key): _summarize_value(child, depth + 1, max_depth, sample_items)
                for key, child in value.items()
            },
        }
    if isinstance(value, (list, tuple)):
        return {
            "type": "array",
            "length": len(value),
            "sample": [
                _summarize_value(child, depth + 1, max_depth, sample_items)
                for child in value[:sample_items]
            ],
        }
    if isinstance(value, str):
        return {"type": "string", "length": len(value), "preview": value[:240]}
    safe_value = _json_safe(value)
    return {"type": type(value).__name__, "value": safe_value}


def _direct_study_query(study_number):
    """Cover common top-level/nested study identifiers before bounded fallback scanning."""
    pattern = re.compile(re.escape(study_number), re.IGNORECASE)
    fields = (
        "study_number",
        "studyNumber",
        "study",
        "study_id",
        "studyId",
        "protocol_number",
        "protocolNumber",
        "metadata.study_number",
        "metadata.studyNumber",
    )
    return {"$or": [{field: pattern} for field in fields]}


@mcp.tool()
def db_list_collections() -> dict:
    """List the data collections available in the LLX document database.

    Use this to discover what internal data exists in the company database.
    This is internal LLX data and has no public/web equivalent.

    (Connectivity check: confirms the cloud server can reach the Cosmos DB.)
    """
    print("[SKILL CALLED] db_list_collections()", flush=True)

    client, db, error = _get_database()
    if error:
        return {"error": error}

    try:
        collections = db.list_collection_names()
        return {
            "database": DATABASE_NAME,
            "collections": collections,
            "count": len(collections),
        }
    except Exception as exc:
        return {"error": f"Could not list database collections ({type(exc).__name__})."}
    finally:
        client.close()


@mcp.tool()
def db_find_documents(
    study_number: str,
    document_type: str = None,
    limit: int = 5,
    include_content: bool = False,
) -> dict:
    """Find how one study document is stored in the `studies` collection.

    This is a specific, read-only inspection tool for company study documents.
    It does not accept arbitrary MongoDB filters or access other collections.

    Args:
        study_number: Study identifier such as "SPI-611".
        document_type: Optional document kind/name such as "SAP", "protocol", or "CRF".
        limit: Maximum matching records to return (1-20, default 5).
        include_content: False returns a nested field/type structure with short previews.
            True returns bounded document JSON (maximum 120,000 characters per record).
    """
    print(
        "[SKILL CALLED] db_find_documents("
        f"study_number={study_number!r}, document_type={document_type!r}, "
        f"limit={limit!r}, include_content={include_content!r})",
        flush=True,
    )

    study_number = (study_number or "").strip()
    document_type = (document_type or "").strip() or None
    if not study_number:
        return {"error": "study_number is required."}
    limit = max(1, min(int(limit), 20))

    client, db, error = _get_database()
    if error:
        return {"error": error}

    collection = db[STUDIES_COLLECTION]
    scanned = 0
    matched = []
    search_mode = "common study fields"

    try:
        try:
            candidates = list(
                collection.find(_direct_study_query(study_number)).limit(MAX_DOCUMENTS_TO_SCAN)
            )
        except Exception:
            candidates = []
        if not candidates:
            search_mode = "bounded schema-agnostic scan"
            candidates = list(collection.find({}).limit(MAX_DOCUMENTS_TO_SCAN))

        for document in candidates:
            scanned += 1
            if not _document_matches(document, study_number, document_type):
                continue

            safe_document = _json_safe(document)
            record = {
                "record_id": str(document.get("_id", "")),
                "top_level_fields": [str(key) for key in document.keys()],
            }
            if include_content:
                serialized = json.dumps(safe_document, ensure_ascii=False, separators=(",", ":"))
                record["document_json"] = serialized[:MAX_RETURNED_CONTENT_CHARS]
                record["content_truncated"] = len(serialized) > MAX_RETURNED_CONTENT_CHARS
                record["original_character_count"] = len(serialized)
            else:
                record["storage_structure"] = _summarize_value(document)
            matched.append(record)
            if len(matched) >= limit:
                break

        return {
            "database": DATABASE_NAME,
            "collection": STUDIES_COLLECTION,
            "study_number": study_number,
            "document_type": document_type,
            "search_mode": search_mode,
            "documents_scanned": scanned,
            "scan_limit": MAX_DOCUMENTS_TO_SCAN,
            "matches_returned": len(matched),
            "include_content": include_content,
            "documents": matched,
        }
    except Exception as exc:
        return {"error": f"Could not inspect study documents ({type(exc).__name__})."}
    finally:
        client.close()
