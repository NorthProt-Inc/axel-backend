"""Lightweight emotion classification using Gemini Flash."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Literal

from google.genai import types

from backend.core.logging import get_logger
from backend.core.utils.gemini_wrapper import get_gemini_wrapper

_log = get_logger("services.emotion")

EmotionLabel = Literal["positive", "negative", "neutral", "mixed"]

_VALID_LABELS: set[str] = {"positive", "negative", "neutral", "mixed"}

_CLASSIFY_PROMPT = (
    "Classify the emotional tone of the following message into exactly ONE word: "
    "positive, negative, neutral, or mixed.\n"
    "Respond with ONLY that single word, nothing else.\n\n"
    "Message: {text}"
)

_CONFIG = types.GenerateContentConfig(
    temperature=0.0,
    max_output_tokens=4,
)

_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="emotion")


def classify_emotion_sync(text: str) -> EmotionLabel:
    """Classify emotion synchronously. Returns 'neutral' on any failure.

    Args:
        text: Message text to classify

    Returns:
        One of: positive, negative, neutral, mixed
    """
    if not text or len(text.strip()) < 2:
        return "neutral"

    try:
        wrapper = get_gemini_wrapper()
        prompt = _CLASSIFY_PROMPT.format(text=text[:500])
        response = wrapper.generate_content_sync(
            contents=prompt,
            generation_config=_CONFIG,
            timeout_seconds=20.0,
        )
        label = response.text.strip().lower()
        if label in _VALID_LABELS:
            _log.debug("emotion_classified", label=label, text_len=len(text))
            return label

        _log.warning("emotion_unexpected_label", raw=label)
        return "neutral"

    except Exception as e:
        _log.warning("emotion_classify_failed", error=str(e)[:100])
        return "neutral"


async def classify_emotion(text: str) -> EmotionLabel:
    """Classify emotion asynchronously. Returns 'neutral' on any failure.

    Args:
        text: Message text to classify

    Returns:
        One of: positive, negative, neutral, mixed
    """
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_executor, classify_emotion_sync, text)
