import csv
import io
import re
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory

from nwis.config import get_settings
from nwis.ingestion.contracts import IngestionFailure
from nwis.ingestion.storage import store_blob


@dataclass
class Page:
    number: int
    text: str
    ocr_applied: bool = False
    ocr_confidence: float | None = None
    preview_key: str | None = None
    word_boxes: list | None = None


def run_command(command: list[str]) -> bytes:
    try:
        return subprocess.run(command, check=True, capture_output=True, timeout=45).stdout
    except FileNotFoundError as exc:
        raise IngestionFailure(
            "tool_unavailable", f"Required tool {command[0]} is unavailable"
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise IngestionFailure(
            "document_timeout", "Page processing exceeded its time limit"
        ) from exc
    except subprocess.CalledProcessError as exc:
        raise IngestionFailure(
            "document_parse_error", "The document could not be parsed or rendered"
        ) from exc


def ocr(image: Path) -> tuple[str, float | None, list]:
    output = run_command(["tesseract", str(image), "stdout", "-l", "eng", "tsv"])
    lines: dict[tuple, list[str]] = {}
    boxes, confidences = [], []
    for item in csv.DictReader(io.StringIO(output.decode()), delimiter="\t"):
        word = (item.get("text") or "").strip()
        if item.get("level") != "5" or not word:
            continue
        key = tuple(item[x] for x in ("block_num", "par_num", "line_num"))
        lines.setdefault(key, []).append(word)
        confidence = float(item["conf"])
        if confidence >= 0:
            confidences.append(confidence / 100)
        boxes.append(
            {"text": word, **{x: int(item[x]) for x in ("left", "top", "width", "height")}}
        )
    return (
        "\n".join(" ".join(words) for words in lines.values()),
        (sum(confidences) / len(confidences) if confidences else None),
        boxes,
    )


def read_pages(
    path: Path, mime_type: str, run_key: str, heartbeat: Callable[[int], None]
) -> list[Page]:
    settings = get_settings()
    if mime_type == "text/plain":
        try:
            pages = [
                Page(i, text)
                for i, text in enumerate(path.read_text(encoding="utf-8").split("\f"), 1)
            ]
        except UnicodeDecodeError as exc:
            raise IngestionFailure("invalid_text", "Text reports must use UTF-8 encoding") from exc
        if len(pages) > settings.document_max_pages:
            raise IngestionFailure("page_limit", "The report exceeds the configured page limit")
        if any(len(page.text) > settings.page_max_characters for page in pages):
            raise IngestionFailure("page_text_limit", "A page exceeds the configured text limit")
        heartbeat(len(pages))
        return pages

    info = run_command(["pdfinfo", str(path)]).decode(errors="replace")
    if re.search(r"Encrypted:\s+yes", info):
        raise IngestionFailure("encrypted_pdf", "Upload an unlocked PDF")
    count_match = re.search(r"^Pages:\s+(\d+)", info, re.MULTILINE)
    if not count_match:
        raise IngestionFailure("invalid_pdf", "PDF page count could not be read")
    count = int(count_match[1])
    if count > settings.document_max_pages:
        raise IngestionFailure("page_limit", "The report exceeds the configured page limit")
    pages = []
    with TemporaryDirectory(prefix="nwis-pages-") as temporary:
        for number in range(1, count + 1):
            heartbeat(number - 1)
            text = (
                run_command(
                    ["pdftotext", "-f", str(number), "-l", str(number), "-layout", str(path), "-"]
                )
                .decode(errors="replace")
                .strip()
            )
            prefix = Path(temporary) / f"page-{number}"
            run_command(
                [
                    "pdftoppm",
                    "-f",
                    str(number),
                    "-l",
                    str(number),
                    "-singlefile",
                    "-scale-to",
                    "1800",
                    "-png",
                    str(path),
                    str(prefix),
                ]
            )
            image = prefix.with_suffix(".png")
            preview_key = f"previews/{run_key}/{number}.png"
            store_blob(preview_key, image.read_bytes())
            page = Page(number, text, preview_key=preview_key, word_boxes=[])
            if len(re.sub(r"\s", "", text)) < 40:
                page.text, page.ocr_confidence, page.word_boxes = ocr(image)
                page.ocr_applied = True
            if len(page.text) > settings.page_max_characters:
                raise IngestionFailure(
                    "page_text_limit", "A page exceeds the configured text limit"
                )
            pages.append(page)
            heartbeat(number)
    return pages
