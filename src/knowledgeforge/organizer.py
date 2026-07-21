"""Safe local organization helpers that do not require a cloud LLM."""

from __future__ import annotations

import re
from collections import Counter

STOPWORDS = {
    "about",
    "after",
    "again",
    "also",
    "and",
    "because",
    "been",
    "before",
    "could",
    "from",
    "have",
    "into",
    "just",
    "like",
    "that",
    "their",
    "there",
    "these",
    "they",
    "this",
    "through",
    "very",
    "want",
    "what",
    "when",
    "where",
    "which",
    "with",
    "would",
    "your",
}


def organize_transcript(text: str) -> dict[str, object]:
    """Produce an editable draft summary and keywords entirely offline.

    This intentionally avoids pretending to be a creative-writing model.  It
    gives users a useful first draft while preserving the complete transcript.
    A provider-backed organizer can later replace this function behind the same
    API contract.
    """
    sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", text.strip()) if part.strip()]
    summary = " ".join(sentences[:3])
    words = re.findall(r"[A-Za-z][A-Za-z'-]{3,}", text.lower())
    tags = [word for word, _ in Counter(word for word in words if word not in STOPWORDS).most_common(8)]
    return {"summary": summary, "tags": tags}
