from datetime import datetime, timezone

from azure.core.exceptions import ResourceNotFoundError
from azure.data.tables import TableServiceClient

from .. import config

_service_client = TableServiceClient.from_connection_string(config.STORAGE_CONNECTION_STRING)


def ensure_tables() -> None:
    _service_client.create_table_if_not_exists(config.JOBS_TABLE_NAME)
    _service_client.create_table_if_not_exists(config.CHAPTERS_TABLE_NAME)


def _jobs_client():
    return _service_client.get_table_client(config.JOBS_TABLE_NAME)


def _chapters_client():
    return _service_client.get_table_client(config.CHAPTERS_TABLE_NAME)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_job(job_id: str, url: str) -> None:
    _jobs_client().create_entity(
        {
            "PartitionKey": "job",
            "RowKey": job_id,
            "url": url,
            "status": "pending",
            "comic": "",
            "chapter": "",
            "chapter_row_key": "",
            "page_count": 0,
            "error": "",
            "created_at": _now(),
        }
    )


def update_job(job_id: str, **fields) -> None:
    entity = {"PartitionKey": "job", "RowKey": job_id, **fields}
    _jobs_client().update_entity(entity, mode="merge")


def get_job(job_id: str) -> dict | None:
    try:
        return dict(_jobs_client().get_entity("job", job_id))
    except ResourceNotFoundError:
        return None


def reconcile_stuck_jobs() -> int:
    """Mark jobs left at status="running" (e.g. from a redeploy mid-scrape) as failed."""
    stuck = _jobs_client().query_entities("status eq 'running'")
    count = 0
    for entity in stuck:
        _jobs_client().update_entity(
            {
                "PartitionKey": entity["PartitionKey"],
                "RowKey": entity["RowKey"],
                "status": "failed",
                "error": "interrupted by app restart",
            },
            mode="merge",
        )
        count += 1
    return count


def upsert_chapter(
    comic: str, chapter_row_key: str, chapter_display: str, page_count: int, source_url: str
) -> None:
    _chapters_client().upsert_entity(
        {
            "PartitionKey": comic,
            "RowKey": chapter_row_key,
            "chapter_display": chapter_display,
            "page_count": page_count,
            "source_url": source_url,
            "created_at": _now(),
        }
    )


def list_comics() -> list[str]:
    entities = _chapters_client().list_entities(select=["PartitionKey"])
    return sorted({e["PartitionKey"] for e in entities})


def list_chapters(comic: str) -> list[dict]:
    escaped = comic.replace("'", "''")
    entities = _chapters_client().query_entities(f"PartitionKey eq '{escaped}'")
    return sorted(entities, key=lambda e: e["RowKey"])


def get_chapter(comic: str, chapter_row_key: str) -> dict | None:
    try:
        return dict(_chapters_client().get_entity(comic, chapter_row_key))
    except ResourceNotFoundError:
        return None
