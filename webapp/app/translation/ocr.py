from dataclasses import dataclass
from io import BytesIO

from azure.ai.vision.imageanalysis import ImageAnalysisClient
from azure.ai.vision.imageanalysis.models import VisualFeatures
from azure.identity import DefaultAzureCredential
from PIL import Image

from .. import config

# Azure Vision's text-detection threshold is calibrated relative to overall
# image resolution (documented minimum: 12px text on a 1024x768 reference
# image). Webtoon-style pages can be extremely tall/narrow (e.g. 720x11000+),
# and that extreme aspect ratio pushes otherwise-normal-sized text below the
# effective detection floor. Splitting into overlapping horizontal strips
# keeps each OCR call at a sane aspect ratio.
STRIP_HEIGHT = 3000
STRIP_OVERLAP = 300


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


def _read_lines_single(image_bytes: bytes) -> list[OcrLine]:
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


def read_lines(image_bytes: bytes) -> list[OcrLine]:
    with Image.open(BytesIO(image_bytes)) as img:
        width, height = img.size
        img = img.convert("RGB")

        if height <= STRIP_HEIGHT * 1.5:
            return _read_lines_single(image_bytes)

        all_lines: list[OcrLine] = []
        seen: set[tuple[str, int, int]] = set()
        y = 0
        while True:
            strip_bottom = min(y + STRIP_HEIGHT, height)
            strip = img.crop((0, y, width, strip_bottom))
            buf = BytesIO()
            strip.save(buf, format="JPEG", quality=90)

            for line in _read_lines_single(buf.getvalue()):
                adjusted = OcrLine(
                    text=line.text,
                    min_x=line.min_x,
                    min_y=line.min_y + y,
                    max_x=line.max_x,
                    max_y=line.max_y + y,
                )
                # De-dupe lines re-detected in the overlap between strips.
                key = (adjusted.text, round(adjusted.min_x / 10), round(adjusted.min_y / 10))
                if key not in seen:
                    seen.add(key)
                    all_lines.append(adjusted)

            if strip_bottom >= height:
                break
            y += STRIP_HEIGHT - STRIP_OVERLAP

        return all_lines
