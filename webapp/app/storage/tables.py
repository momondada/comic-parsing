from datetime import datetime, timezone

from azure.core.exceptions import ResourceNotFoundError
from azure.data.tables import TableServiceClient
from azure.identity import DefaultAzureCredential

from .. import config


def _make_client() -> TableServiceClient:
    if config.STORAGE_CONNECTION_STRING:
        return TableServiceClient.from_connection_string(config.STORAGE_CONNECTION_STRING)
    account_url = f"https://{config.STORAGE_ACCOUNT_NAME}.table.core.windows.net"
    return TableServiceClient(account_url, credential=DefaultAzureCredential())


_service_client = _make_client()


def ensure_tables() -> None:
    _service_client.create_table_if_not_exists(config.JOBS_TABLE_NAME)
    _service_client.create_table_if_not_exists(config.CHAPTERS_TABLE_NAME)
    _service_client.create_table_if_not_exists(config.COMICS_TABLE_NAME)
    _service_client.create_table_if_not_exists(config.BATCHES_TABLE_NAME)


def _jobs_client():
    return _service_client.get_table_client(config.JOBS_TABLE_NAME)


def _chapters_client():
    return _service_client.get_table_client(config.CHAPTERS_TABLE_NAME)


def _comics_client():
    return _service_client.get_table_client(config.COMICS_TABLE_NAME)


def _batches_client():
    return _service_client.get_table_client(config.BATCHES_TABLE_NAME)


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


def mark_chapter_translated(comic: str, chapter_row_key: str) -> None:
    _chapters_client().update_entity(
        {
            "PartitionKey": comic,
            "RowKey": chapter_row_key,
            "translated": True,
            "translated_at": _now(),
        },
        mode="merge",
    )


def upsert_comic_template(comic: str, url_template: str) -> None:
    _comics_client().upsert_entity(
        {"PartitionKey": "comic", "RowKey": comic, "url_template": url_template}
    )


def _get_comic_entity(comic: str) -> dict | None:
    try:
        return dict(_comics_client().get_entity("comic", comic))
    except ResourceNotFoundError:
        return None


def get_comic_template(comic: str) -> str | None:
    entity = _get_comic_entity(comic)
    return entity.get("url_template") if entity else None


def set_comic_display_name(comic: str, display_name: str) -> None:
    _comics_client().upsert_entity(
        {"PartitionKey": "comic", "RowKey": comic, "display_name": display_name}
    )


def get_comic_display_names(comics: list[str]) -> dict[str, str]:
    """Display name per comic slug, falling back to the slug itself if unset."""
    names = {}
    for comic in comics:
        entity = _get_comic_entity(comic)
        names[comic] = (entity.get("display_name") if entity else None) or comic
    return names


def set_work_kind(comic: str, kind: str) -> None:
    _comics_client().upsert_entity({"PartitionKey": "comic", "RowKey": comic, "kind": kind})


def get_work_kind(comic: str) -> str:
    """"comic" (default, for entries predating this field) or "novel"."""
    entity = _get_comic_entity(comic)
    return (entity.get("kind") if entity else None) or "comic"


def create_batch(batch_id: str, comic: str, start: int, end: int) -> None:
    _batches_client().create_entity(
        {
            "PartitionKey": "batch",
            "RowKey": batch_id,
            "comic": comic,
            "start": start,
            "end": end,
            "total": end - start + 1,
            "done": 0,
            "skipped": 0,
            "failed": 0,
            "current_chapter": "",
            "status": "pending",
            "error": "",
            "created_at": _now(),
        }
    )


def update_batch(batch_id: str, **fields) -> None:
    entity = {"PartitionKey": "batch", "RowKey": batch_id, **fields}
    _batches_client().update_entity(entity, mode="merge")


def increment_batch(batch_id: str, **counters) -> None:
    client = _batches_client()
    entity = client.get_entity("batch", batch_id)
    for key, amount in counters.items():
        entity[key] = entity.get(key, 0) + amount
    client.update_entity(entity, mode="merge")


def get_batch(batch_id: str) -> dict | None:
    try:
        return dict(_batches_client().get_entity("batch", batch_id))
    except ResourceNotFoundError:
        return None
