from .. import config
from .openai_client import get_openai_client

INSTRUCTIONS = (
    "You will receive one chapter of a Japanese web novel as plain text, "
    "one paragraph per line. Translate it into natural, fluent Traditional "
    "Chinese (zh-Hant), preserving the original paragraph breaks exactly "
    "(same number of lines, same order). Respond with ONLY the translated "
    "text — no commentary, no markdown, no line numbering."
)


def translate_chapter(text: str) -> str:
    client = get_openai_client()
    response = client.responses.create(
        model=config.AZURE_OPENAI_DEPLOYMENT,
        instructions=INSTRUCTIONS,
        input=text,
        max_output_tokens=8000,
    )
    return response.output_text
