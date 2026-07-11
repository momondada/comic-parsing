import os

# Local/Azurite dev: set AZURE_STORAGE_CONNECTION_STRING (key-based auth).
# Real Azure deploy: set AZURE_STORAGE_ACCOUNT_NAME instead — the app
# authenticates via the Web App's Managed Identity (some tenants disable
# storage account key access via policy, so key-based auth can't be assumed).
STORAGE_CONNECTION_STRING = os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
STORAGE_ACCOUNT_NAME = os.environ.get("AZURE_STORAGE_ACCOUNT_NAME")

if not STORAGE_CONNECTION_STRING and not STORAGE_ACCOUNT_NAME:
    raise RuntimeError(
        "Set AZURE_STORAGE_CONNECTION_STRING (local/Azurite) or "
        "AZURE_STORAGE_ACCOUNT_NAME (Azure, uses Managed Identity)"
    )

BLOB_CONTAINER_NAME = os.environ.get("BLOB_CONTAINER_NAME", "comic-pages")
JOBS_TABLE_NAME = os.environ.get("JOBS_TABLE_NAME", "jobs")
CHAPTERS_TABLE_NAME = os.environ.get("CHAPTERS_TABLE_NAME", "chapters")
COMICS_TABLE_NAME = os.environ.get("COMICS_TABLE_NAME", "comics")
BATCHES_TABLE_NAME = os.environ.get("BATCHES_TABLE_NAME", "batches")

# Translation overlay: no local emulator exists for Cognitive Services, so
# AI_SERVICES_KEY (optional) lets local dev hit a real resource with a key;
# on Azure this is left unset and DefaultAzureCredential (Managed Identity)
# is used instead, matching the storage auth pattern above.
_ai_services_endpoint_raw = os.environ.get("AZURE_AI_SERVICES_ENDPOINT")
# Strip any trailing slash: the SDKs append their own path (e.g.
# /translator/text/v...), and a double slash in that join 404s at the gateway.
AI_SERVICES_ENDPOINT = (
    _ai_services_endpoint_raw.rstrip("/") if _ai_services_endpoint_raw else None
)
AI_SERVICES_KEY = os.environ.get("AZURE_AI_SERVICES_KEY")
# Required for the Translator API specifically when authenticating with a
# token (Managed Identity) against a multi-service resource's own endpoint —
# the service uses these to resolve which resource the token is for.
AI_SERVICES_REGION = os.environ.get("AZURE_AI_SERVICES_REGION")
AI_SERVICES_RESOURCE_ID = os.environ.get("AZURE_AI_SERVICES_RESOURCE_ID")
TRANSLATE_TARGET_LANGUAGE = os.environ.get("TRANSLATE_TARGET_LANGUAGE", "zh-Hant")
