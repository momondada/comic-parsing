import base64
import json
from dataclasses import dataclass

import requests
from azure.identity import DefaultAzureCredential

from .. import config

API_VERSION = "2024-10-21"
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

_credential = None


@dataclass
class Bubble:
    text_zh: str
    left_pct: float
    top_pct: float
    width_pct: float
    height_pct: float


def _get_token() -> str:
    global _credential
    if _credential is None:
        _credential = DefaultAzureCredential()
    return _credential.get_token(TOKEN_SCOPE).token


def translate_page(image_bytes: bytes) -> list[Bubble]:
    b64 = base64.b64encode(image_bytes).decode("ascii")
    url = (
        f"{config.AI_SERVICES_ENDPOINT}/openai/deployments/"
        f"{config.AZURE_OPENAI_DEPLOYMENT}/chat/completions"
    )

    headers = {"Content-Type": "application/json"}
    if config.AI_SERVICES_KEY:
        headers["api-key"] = config.AI_SERVICES_KEY
    else:
        headers["Authorization"] = f"Bearer {_get_token()}"

    body = {
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
                    }
                ],
            },
        ],
        "response_format": {"type": "json_object"},
        "max_tokens": 4000,
    }

    response = requests.post(
        url,
        params={"api-version": API_VERSION},
        headers=headers,
        json=body,
        timeout=60,
    )
    response.raise_for_status()

    content = response.json()["choices"][0]["message"]["content"]
    data = json.loads(content)

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
