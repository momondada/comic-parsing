import time

import openai

from .. import config
from .openai_client import get_openai_client

INSTRUCTIONS = (
    "You will receive one chapter of a Japanese web novel as plain text, "
    "one paragraph per line. Translate it into natural, fluent Traditional "
    "Chinese (zh-Hant), preserving the original paragraph breaks exactly "
    "(same number of lines, same order). Respond with ONLY the translated "
    "text — no commentary, no markdown, no line numbering."
)

# A ~150-chapter novel means ~150 sequential calls in a short window, which
# can trip the deployment's requests/tokens-per-minute quota partway
# through. Without a retry, a single 429 mid-batch would otherwise fall
# back to the untranslated original for every remaining chapter.
MAX_RETRIES = 5
BASE_BACKOFF_SECONDS = 5


def translate_chapter(text: str) -> str:
    client = get_openai_client()
    last_error = None

    for attempt in range(MAX_RETRIES):
        try:
            response = client.responses.create(
                model=config.AZURE_OPENAI_DEPLOYMENT,
                instructions=INSTRUCTIONS,
                input=text,
                max_output_tokens=8000,
            )
            return response.output_text
        except openai.RateLimitError as e:
            last_error = e
            time.sleep(BASE_BACKOFF_SECONDS * (2**attempt))

    raise last_error
