import base64
import json

from azure.identity import DefaultAzureCredential
from dataclasses import dataclass
from openai import AzureOpenAI

from .. import config

API_VERSION = "2025-04-01-preview"
TOKEN_SCOPE = "https://cognitiveservices.azure.com/.default"

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

_credential = None


@dataclass
class Bubble:
    text_zh: str
    left_pct: float
    top_pct: float
    width_pct: float
    height_pct: float


def _get_client() -> AzureOpenAI:
    global _credential
    if config.AI_SERVICES_KEY:
        return AzureOpenAI(
            api_key=config.AI_SERVICES_KEY,
            api_version=API_VERSION,
            azure_endpoint=config.AI_SERVICES_ENDPOINT,
        )
    if _credential is None:
        _credential = DefaultAzureCredential()
    token = _credential.get_token(TOKEN_SCOPE).token
    return AzureOpenAI(
        azure_ad_token=token,
        api_version=API_VERSION,
        azure_endpoint=config.AI_SERVICES_ENDPOINT,
    )


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
        max_output_tokens=4000,
    )

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
