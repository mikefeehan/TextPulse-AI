from __future__ import annotations

import hashlib
import math
import re
from collections import Counter
from datetime import datetime

STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "at",
    "be",
    "but",
    "for",
    "from",
    "i",
    "if",
    "in",
    "is",
    "it",
    "just",
    "me",
    "my",
    "of",
    "on",
    "or",
    "so",
    "that",
    "the",
    "to",
    "we",
    "you",
    "your",
}

POSITIVE_WORDS = {
    "amazing",
    "awesome",
    "beautiful",
    "excited",
    "glad",
    "great",
    "haha",
    "happy",
    "love",
    "miss",
    "nice",
    "perfect",
    "thank",
    "yay",
}

NEGATIVE_WORDS = {
    "annoying",
    "angry",
    "busy",
    "cold",
    "confused",
    "hate",
    "mad",
    "sorry",
    "stressed",
    "tired",
    "ugh",
    "upset",
    "whatever",
    "worried",
}

EMOJI_PATTERN = re.compile(
    "["
    "\U0001F300-\U0001F5FF"
    "\U0001F600-\U0001F64F"
    "\U0001F680-\U0001F6FF"
    "\U0001F900-\U0001F9FF"
    "\u2600-\u26FF"
    "\u2700-\u27BF"
    "]+",
    flags=re.UNICODE,
)

WORD_PATTERN = re.compile(r"[A-Za-z0-9']+")


def tokenize(text: str) -> list[str]:
    return [word.lower() for word in WORD_PATTERN.findall(text)]


def keyword_counts(texts: list[str]) -> Counter[str]:
    counter: Counter[str] = Counter()
    for text in texts:
        for token in tokenize(text):
            if token not in STOPWORDS and len(token) > 2:
                counter[token] += 1
    return counter


def sentiment_score(text: str) -> float:
    tokens = tokenize(text)
    if not tokens:
        return 0.0
    score = sum(1 for token in tokens if token in POSITIVE_WORDS) - sum(
        1 for token in tokens if token in NEGATIVE_WORDS
    )
    punctuation_boost = text.count("!") * 0.05
    return max(-1.0, min(1.0, (score / max(len(tokens), 1)) * 3 + punctuation_boost))


def count_emojis(text: str) -> Counter[str]:
    counter: Counter[str] = Counter()
    for match in EMOJI_PATTERN.findall(text):
        for emoji in match:
            counter[emoji] += 1
    return counter


def deterministic_embedding(text: str, dimensions: int = 24) -> list[float]:
    vector = [0.0] * dimensions
    tokens = tokenize(text)
    if not tokens:
        return vector

    for token in tokens:
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        for index in range(dimensions):
            raw = digest[index] / 255.0
            vector[index] += (raw * 2) - 1

    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [round(value / norm, 6) for value in vector]


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    return sum(left * right for left, right in zip(a, b, strict=False))


def month_bucket(timestamp: datetime) -> str:
    return timestamp.strftime("%Y-%m")
