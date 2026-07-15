import json

from .. import config
from .openai_client import get_openai_client

CHUNK_SIZE = 40

INSTRUCTIONS = (
    "You will receive a JSON array of objects, each with an integer id and "
    "raw OCR-extracted comic dialogue text. Comic lettering is "
    "conventionally printed in ALL CAPS. For each object, return: (1) "
    "text_en: the same text normalized to natural sentence case (e.g. "
    '"THIS IS A BOOK." becomes "This is a book."), preserving genuine '
    "acronyms, proper nouns, or emphasis from the original (if the source "
    "text is not English, leave text_en as the original text unchanged), "
    "and (2) text_zh: its Traditional Chinese (zh-Hant) translation. "
    "Respond with ONLY JSON, no markdown, in this exact shape: "
    '{"items": [{"id": 0, "text_en": "...", "text_zh": "..."}, ...]}. '
    "You MUST include the same id from the input on every output item — "
    "this is how results get matched back to their source text, so a "
    "missing or wrong id will corrupt the result. Include every id "
    "exactly once; order doesn't matter."
)


def _translate_chunk(items: list[tuple[int, str]]) -> dict[int, tuple[str, str]]:
    client = get_openai_client()
    payload = [{"id": i, "text": text} for i, text in items]
    response = client.responses.create(
        model=config.AZURE_OPENAI_DEPLOYMENT,
        instructions=INSTRUCTIONS,
        input=json.dumps(payload, ensure_ascii=False),
        max_output_tokens=4000,
    )

    if not response.output_text:
        print(
            f"[diagnostic] empty output_text, raw response: {response.model_dump_json()}",
            flush=True,
        )

    data = json.loads(response.output_text)
    return {entry["id"]: (entry["text_en"], entry["text_zh"]) for entry in data["items"]}


def normalize_and_translate(texts: list[str]) -> list[tuple[str, str]]:
    """Given raw OCR text per bubble, return (normalized_en, zh) pairs.

    Pure text in/out — no image involved, so this doesn't depend on a
    vision model's ability to also localize bubbles (that's OCR's job).
    Results are matched back to their input by an explicit id rather than
    assuming the model preserves array order/count, since a chapter can
    have 100+ bubbles and a positional mismatch silently corrupts every
    bubble after the first dropped/reordered one.
    """
    if not texts:
        return []

    indexed = list(enumerate(texts))
    by_id: dict[int, tuple[str, str]] = {}

    for start in range(0, len(indexed), CHUNK_SIZE):
        by_id.update(_translate_chunk(indexed[start : start + CHUNK_SIZE]))

    return [by_id.get(i, (text, text)) for i, text in indexed]
