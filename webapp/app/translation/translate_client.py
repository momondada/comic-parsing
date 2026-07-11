from azure.ai.translation.text import TextTranslationClient
from azure.identity import DefaultAzureCredential

from .. import config

MAX_BATCH_SIZE = 900  # service limit is 1000 elements per request


def _make_translator_client() -> TextTranslationClient:
    if config.AI_SERVICES_KEY:
        from azure.core.credentials import AzureKeyCredential

        return TextTranslationClient(
            endpoint=config.AI_SERVICES_ENDPOINT,
            credential=AzureKeyCredential(config.AI_SERVICES_KEY),
        )
    return TextTranslationClient(
        endpoint=config.AI_SERVICES_ENDPOINT, credential=DefaultAzureCredential()
    )


_client = None


def _get_client() -> TextTranslationClient:
    global _client
    if _client is None:
        _client = _make_translator_client()
    return _client


def translate_texts(texts: list[str], to_language: str | None = None) -> list[str]:
    if not texts:
        return []

    target = to_language or config.TRANSLATE_TARGET_LANGUAGE
    client = _get_client()
    results: list[str] = []

    for start in range(0, len(texts), MAX_BATCH_SIZE):
        chunk = texts[start : start + MAX_BATCH_SIZE]
        response = client.translate(body=chunk, to_language=[target])
        results.extend(item.translations[0].text for item in response)

    return results
