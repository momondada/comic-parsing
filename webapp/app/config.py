import os

STORAGE_CONNECTION_STRING = os.environ["AZURE_STORAGE_CONNECTION_STRING"]
BLOB_CONTAINER_NAME = os.environ.get("BLOB_CONTAINER_NAME", "comic-pages")
JOBS_TABLE_NAME = os.environ.get("JOBS_TABLE_NAME", "jobs")
CHAPTERS_TABLE_NAME = os.environ.get("CHAPTERS_TABLE_NAME", "chapters")
