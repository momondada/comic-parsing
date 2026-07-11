from dataclasses import dataclass

from azure.ai.vision.imageanalysis import ImageAnalysisClient
from azure.ai.vision.imageanalysis.models import VisualFeatures
from azure.identity import DefaultAzureCredential

from .. import config


def _make_vision_client() -> ImageAnalysisClient:
    if config.AI_SERVICES_KEY:
        from azure.core.credentials import AzureKeyCredential

        return ImageAnalysisClient(
            endpoint=config.AI_SERVICES_ENDPOINT,
            credential=AzureKeyCredential(config.AI_SERVICES_KEY),
        )
    return ImageAnalysisClient(
        endpoint=config.AI_SERVICES_ENDPOINT, credential=DefaultAzureCredential()
    )


_client = None


def _get_client() -> ImageAnalysisClient:
    global _client
    if _client is None:
        _client = _make_vision_client()
    return _client


@dataclass
class OcrLine:
    text: str
    min_x: float
    min_y: float
    max_x: float
    max_y: float


def read_lines(image_bytes: bytes) -> list[OcrLine]:
    result = _get_client().analyze(image_data=image_bytes, visual_features=[VisualFeatures.READ])

    lines: list[OcrLine] = []
    if not result.read:
        return lines

    for block in result.read.blocks:
        for line in block.lines:
            xs = [point.x for point in line.bounding_polygon]
            ys = [point.y for point in line.bounding_polygon]
            lines.append(
                OcrLine(
                    text=line.text,
                    min_x=min(xs),
                    min_y=min(ys),
                    max_x=max(xs),
                    max_y=max(ys),
                )
            )
    return lines
