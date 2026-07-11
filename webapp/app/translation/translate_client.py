import requests
from azure.identity import DefaultAzureCredential

from .. import config

MAX_BATCH_SIZE = 900  # service limit is 1000 elements per request
TOKEN_SCOPE = "https://cognitiveservices.azure.com/.default"
GLOBAL_ENDPOINT = "https://api.cognitive.microsofttranslator.com/translate"

_credential = None


def _get_token() -> str:
    global _credential
    if _credential is None:
        _credential = DefaultAzureCredential()
    return _credential.get_token(TOKEN_SCOPE).token


def _translate_chunk(chunk: list[str], target: str) -> list[str]:
    headers = {"Content-Type": "application/json"}

    if config.AI_SERVICES_KEY:
        headers["Ocp-Apim-Subscription-Key"] = config.AI_SERVICES_KEY
        headers["Ocp-Apim-Subscription-Region"] = config.AI_SERVICES_REGION
    else:
        headers["Authorization"] = f"Bearer {_get_token()}"
        headers["Ocp-Apim-ResourceId"] = config.AI_SERVICES_RESOURCE_ID
        headers["Ocp-Apim-Subscription-Region"] = config.AI_SERVICES_REGION

    response = requests.post(
        GLOBAL_ENDPOINT,
        params={"api-version": "3.0", "to": target},
        headers=headers,
        json=[{"text": text} for text in chunk],
        timeout=30,
    )
    response.raise_for_status()
    return [item["translations"][0]["text"] for item in response.json()]


def translate_texts(texts: list[str], to_language: str | None = None) -> list[str]:
    if not texts:
        return []

    target = to_language or config.TRANSLATE_TARGET_LANGUAGE
    results: list[str] = []

    for start in range(0, len(texts), MAX_BATCH_SIZE):
        chunk = texts[start : start + MAX_BATCH_SIZE]
        results.extend(_translate_chunk(chunk, target))

    return results
