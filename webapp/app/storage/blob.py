from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient

from .. import config
from ..scraping.capture import CapturedImage


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
        blob_name = f"{comic}/{chapter_row_key}/{idx:03d}.jpg"
        container.upload_blob(
            blob_name, image.body, overwrite=True, content_type="image/jpeg"
        )
    return len(images)


def list_page_filenames(comic: str, chapter_row_key: str) -> list[str]:
    prefix = f"{comic}/{chapter_row_key}/"
    blobs = _container().list_blobs(name_starts_with=prefix)
    names = [b.name[len(prefix) :] for b in blobs]
    return sorted(names)


def download_page(comic: str, chapter_row_key: str, filename: str) -> bytes:
    blob_name = f"{comic}/{chapter_row_key}/{filename}"
    return _container().download_blob(blob_name).readall()
