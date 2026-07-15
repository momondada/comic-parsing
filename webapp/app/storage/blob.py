import json

from azure.core.exceptions import ResourceNotFoundError
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient

from .. import config
from ..scraping.capture import CapturedImage, get_filename_from_url

CONTENT_TYPES = {
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "webp": "image/webp",
    "gif": "image/gif",
}


def _make_client() -> BlobServiceClient:
    if config.STORAGE_CONNECTION_STRING:
        return BlobServiceClient.from_connection_string(config.STORAGE_CONNECTION_STRING)
    account_url = f"https://{config.STORAGE_ACCOUNT_NAME}.blob.core.windows.net"
    return BlobServiceClient(account_url, credential=DefaultAzureCredential())


_service_client = _make_client()


def ensure_container() -> None:
    container = _service_client.get_container_client(config.BLOB_CONTAINER_NAME)
    if not container.exists():
        container.create_container()


def _container():
    return _service_client.get_container_client(config.BLOB_CONTAINER_NAME)


def upload_chapter_images(comic: str, chapter_row_key: str, images: list[CapturedImage]) -> int:
    container = _container()
    for idx, image in enumerate(images, start=1):
        source_name = get_filename_from_url(image.url)
        ext = source_name.rsplit(".", 1)[-1].lower() if "." in source_name else "jpg"
        blob_name = f"{comic}/{chapter_row_key}/{idx:03d}.{ext}"
        container.upload_blob(
            blob_name,
            image.body,
            overwrite=True,
            content_type=CONTENT_TYPES.get(ext, "image/jpeg"),
        )
    return len(images)


def list_page_filenames(comic: str, chapter_row_key: str) -> list[str]:
    prefix = f"{comic}/{chapter_row_key}/"
    blobs = _container().list_blobs(name_starts_with=prefix)
    names = [b.name[len(prefix) :] for b in blobs]
    # translations.json lives alongside the page images under the same
    # prefix but isn't a page itself.
    names = [n for n in names if not n.endswith(".json")]
    return sorted(names)


def download_page(comic: str, chapter_row_key: str, filename: str) -> bytes:
    blob_name = f"{comic}/{chapter_row_key}/{filename}"
    return _container().download_blob(blob_name).readall()


def upload_chapter_translations(comic: str, chapter_row_key: str, data: dict) -> None:
    blob_name = f"{comic}/{chapter_row_key}/translations.json"
    _container().upload_blob(
        blob_name,
        json.dumps(data).encode("utf-8"),
        overwrite=True,
        content_type="application/json",
    )


def download_chapter_translations(comic: str, chapter_row_key: str) -> dict | None:
    blob_name = f"{comic}/{chapter_row_key}/translations.json"
    try:
        raw = _container().download_blob(blob_name).readall()
    except ResourceNotFoundError:
        return None
    return json.loads(raw)


def upload_novel_chapter(novel: str, chapter_row_key: str, label: str, text_zh: str) -> None:
    blob_name = f"{novel}/{chapter_row_key}/text.json"
    _container().upload_blob(
        blob_name,
        json.dumps({"label": label, "text_zh": text_zh}).encode("utf-8"),
        overwrite=True,
        content_type="application/json",
    )


def download_novel_chapter(novel: str, chapter_row_key: str) -> dict | None:
    blob_name = f"{novel}/{chapter_row_key}/text.json"
    try:
        raw = _container().download_blob(blob_name).readall()
    except ResourceNotFoundError:
        return None
    return json.loads(raw)


def upload_novel_combined(novel: str, text: str) -> None:
    blob_name = f"{novel}/combined.txt"
    _container().upload_blob(
        blob_name, text.encode("utf-8"), overwrite=True, content_type="text/plain; charset=utf-8"
    )


def download_novel_combined(novel: str) -> bytes | None:
    blob_name = f"{novel}/combined.txt"
    try:
        return _container().download_blob(blob_name).readall()
    except ResourceNotFoundError:
        return None
