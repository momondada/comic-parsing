from azure.ai.translation.text import TextTranslationClient
from azure.identity import DefaultAzureCredential

from .. import config

MAX_BATCH_SIZE = 900  # service limit is 1000 elements per request


def _make_translator_client() -> TextTranslationClient:
    # Use the default global endpoint (not the AIServices custom domain —
    # that 404s for Translator specifically) with region + resource_id to
    # identify the multi-service resource, per Translator's documented
    # Entra ID auth pattern for multi-service resources.
    if config.AI_SERVICES_KEY:
        from azure.core.credentials import AzureKeyCredential

        return TextTranslationClient(
            credential=AzureKeyCredential(config.AI_SERVICES_KEY),
            region=config.AI_SERVICES_REGION,
        )
    return TextTranslationClient(
        credential=DefaultAzureCredential(),
        region=config.AI_SERVICES_REGION,
        resource_id=config.AI_SERVICES_RESOURCE_ID,
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
