import re
from difflib import SequenceMatcher


def normalize_query_text(value: str) -> str:
    value = value.casefold()
    value = re.sub(r"[\[\]\(\)（）【】]", " ", value)
    value = re.sub(r"[^\w\u3040-\u30ff\u3400-\u9fff]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def strip_bracketed_text(value: str) -> str:
    value = re.sub(r"[\[\(（【].*?[\]\)）】]", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def text_similarity(left: str, right: str) -> float:
    left = normalize_query_text(left)
    right = normalize_query_text(right)
    if not left or not right:
        return 0.0
    if left == right:
        return 1.0
    return SequenceMatcher(None, left, right).ratio()


def contains_meaningful_text(haystack: str, needle: str) -> bool:
    haystack = normalize_query_text(haystack)
    needle = normalize_query_text(needle)
    return bool(needle and len(needle) >= 3 and needle in haystack)


def unique_nonempty(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        value = re.sub(r"\s+", " ", value).strip()
        if not value:
            continue
        key = normalize_query_text(value)
        if key in seen:
            continue
        seen.add(key)
        result.append(value)
    return result

