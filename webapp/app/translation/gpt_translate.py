import base64
import json
from dataclasses import dataclass

from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from openai import OpenAI

from .. import config

TOKEN_SCOPE = "https://ai.azure.com/.default"

SYSTEM_PROMPT = (
    "You are analyzing a single comic/manga page image. Identify every "
    "dialogue or speech bubble that contains English text. For each bubble, "
    "translate the text into Traditional Chinese (zh-Hant) and estimate its "
    "bounding box as percentages of the full image width/height, where "
    "(0, 0) is the top-left corner. Respond with ONLY JSON, no markdown, "
    'in this exact shape: {"bubbles": [{"text_zh": "...", "left_pct": 0.0, '
    '"top_pct": 0.0, "width_pct": 0.0, "height_pct": 0.0}, ...]}. If there '
    'is no text on the page, respond with {"bubbles": []}.'
)

_client = None


@dataclass
class Bubble:
    text_zh: str
    left_pct: float
    top_pct: float
    width_pct: float
    height_pct: float


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        if config.AI_SERVICES_KEY:
            _client = OpenAI(base_url=config.AI_SERVICES_ENDPOINT, api_key=config.AI_SERVICES_KEY)
        else:
            token_provider = get_bearer_token_provider(DefaultAzureCredential(), TOKEN_SCOPE)
            _client = OpenAI(base_url=config.AI_SERVICES_ENDPOINT, api_key=token_provider)
    return _client


def translate_page(image_bytes: bytes) -> list[Bubble]:
    b64 = base64.b64encode(image_bytes).decode("ascii")
    client = _get_client()

    response = client.responses.create(
        model=config.AZURE_OPENAI_DEPLOYMENT,
        instructions=SYSTEM_PROMPT,
        input=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_image",
                        "image_url": f"data:image/jpeg;base64,{b64}",
                    }
                ],
            }
        ],
        # gpt-5.4-pro is a reasoning model — its (invisible) reasoning tokens
        # count against max_output_tokens too, and a low budget can be
        # entirely consumed by reasoning with zero room left for the actual
        # answer (observed: 4000/4000 spent on reasoning, response
        # "incomplete"). This "pro" tier only supports medium/high/xhigh
        # effort (low is rejected), so use the lowest supported tier and
        # give it a generous budget so reasoning doesn't crowd out the
        # real JSON answer on a busy page.
        reasoning={"effort": "medium"},
        max_output_tokens=32000,
    )

    if not response.output_text:
        print(f"[diagnostic] empty output_text, raw response: {response.model_dump_json()}", flush=True)

    data = json.loads(response.output_text)

    return [
        Bubble(
            text_zh=b["text_zh"],
            left_pct=b["left_pct"],
            top_pct=b["top_pct"],
            width_pct=b["width_pct"],
            height_pct=b["height_pct"],
        )
        for b in data.get("bubbles", [])
    ]
