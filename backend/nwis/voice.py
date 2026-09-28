"""Local-only voice transcription. Audio never goes to an external ASR service."""

import importlib.util
import math
from dataclasses import dataclass
from pathlib import Path

from nwis.config import get_settings
from nwis.ingestion.contracts import IngestionFailure

LANGUAGES = {"as", "hi", "en"}


@dataclass(frozen=True)
class Transcript:
    text: str
    language: str
    confidence: float | None
    confidence_kind: str | None


def local_asr_available() -> bool:
    model_path = get_settings().voice_model_path
    return bool(model_path and model_path.is_dir()
                and importlib.util.find_spec("faster_whisper") is not None)


def transcribe_local(audio_path: Path, language: str) -> Transcript:
    if language not in LANGUAGES:
        raise IngestionFailure("voice_language_unsupported", "Select Assamese, Hindi or English")
    if not local_asr_available():
        raise IngestionFailure("local_asr_unavailable", "Install a local multilingual ASR model or provide a typed transcript")
    # A verified local directory plus local_files_only prevents implicit model downloads.
    from faster_whisper import WhisperModel  # type: ignore[import-not-found]

    model = WhisperModel(str(get_settings().voice_model_path), device="cpu",
                         compute_type="int8", local_files_only=True)
    segments, _info = model.transcribe(str(audio_path), language=language,
                                      beam_size=1, condition_on_previous_text=False)
    materialized = list(segments)
    text = " ".join(item.text.strip() for item in materialized if item.text.strip()).strip()
    if not text:
        raise IngestionFailure("empty_voice_transcript", "No speech could be transcribed locally")
    if len(text) > get_settings().page_max_characters:
        raise IngestionFailure("page_text_limit", "Voice transcript exceeds the page text limit")
    scores = [math.exp(max(-20.0, min(0.0, item.avg_logprob))) for item in materialized
              if item.text.strip() and math.isfinite(item.avg_logprob)]
    # Mean token likelihood is an uncalibrated diagnostic, never approval confidence.
    confidence = sum(scores) / len(scores) if scores else None
    return Transcript(text=text, language=language, confidence=confidence,
                      confidence_kind="uncalibrated_token_likelihood" if confidence is not None else None)


def typed_transcript(text: str, language: str) -> Transcript:
    if language not in LANGUAGES:
        raise IngestionFailure("voice_language_unsupported", "Select Assamese, Hindi or English")
    cleaned = text.strip()
    if not cleaned or len(cleaned) > get_settings().page_max_characters:
        raise IngestionFailure("invalid_typed_transcript", "Provide a transcript within the page text limit")
    return Transcript(text=cleaned, language=language, confidence=None, confidence_kind=None)
