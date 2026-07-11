import json

from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from openai import OpenAI

from .. import config

TOKEN_SCOPE = "https://ai.azure.com/.default"
CHUNK_SIZE = 150

INSTRUCTIONS = (
    "You will receive a JSON array of raw OCR-extracted comic dialogue "
    "lines. Comic lettering is conventionally printed in ALL CAPS. For "
    "each input string, return: (1) text_en: the same text normalized to "
    'natural sentence case (e.g. "THIS IS A BOOK." becomes "This is a '
    'book."), preserving genuine acronyms, proper nouns, or emphasis from '
    "the original, and (2) text_zh: its Traditional Chinese (zh-Hant) "
    "translation. Respond with ONLY JSON, no markdown, in this exact "
    'shape: {"items": [{"text_en": "...", "text_zh": "..."}, ...]}, with '
    "exactly one item per input string, in the same order as the input."
)

_client = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        if config.AZURE_OPENAI_KEY:
            _client = OpenAI(base_url=config.AZURE_OPENAI_ENDPOINT, api_key=config.AZURE_OPENAI_KEY)
        else:
            token_provider = get_bearer_token_provider(DefaultAzureCredential(), TOKEN_SCOPE)
            _client = OpenAI(base_url=config.AZURE_OPENAI_ENDPOINT, api_key=token_provider)
    return _client


def _translate_chunk(texts: list[str]) -> list[tuple[str, str]]:
    client = _get_client()
    response = client.responses.create(
        model=config.AZURE_OPENAI_DEPLOYMENT,
        instructions=INSTRUCTIONS,
        input=json.dumps(texts, ensure_ascii=False),
        max_output_tokens=8000,
    )

    if not response.output_text:
        print(
            f"[diagnostic] empty output_text, raw response: {response.model_dump_json()}",
            flush=True,
        )

    data = json.loads(response.output_text)
    return [(item["text_en"], item["text_zh"]) for item in data["items"]]


def normalize_and_translate(texts: list[str]) -> list[tuple[str, str]]:
    """Given raw OCR text per bubble, return (normalized_en, zh) pairs.

    Pure text in/out — no image involved, so this doesn't depend on a
    vision model's ability to also localize bubbles (that's OCR's job).
    """
    if not texts:
        return []

    results: list[tuple[str, str]] = []
    for start in range(0, len(texts), CHUNK_SIZE):
        results.extend(_translate_chunk(texts[start : start + CHUNK_SIZE]))
    return results
