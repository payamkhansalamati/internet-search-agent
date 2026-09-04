import re

LABEL = re.compile(r"^(?:\d{1,5}|[ivxlcdm]{1,12}|[^\W\d_]{1,8}[-–]\d{1,5})$", re.I)
ROMAN_VALUES = {"i": 1, "v": 5, "x": 10, "l": 50, "c": 100, "d": 500, "m": 1000}


def resolve_printed_pages(texts: list[str], metadata_labels: list[str] | None = None) -> list[str | None]:
    """Resolve printed labels without assuming a document-specific page offset."""
    if metadata_labels is not None:
        return [str(label).strip() or None for label in metadata_labels[: len(texts)]] + [None] * max(
            0, len(texts) - len(metadata_labels)
        )

    candidates = [_boundary_candidates(text) for text in texts]
    resolved: list[str | None] = [None] * len(texts)
    for boundary_position in range(4):
        series = [items[boundary_position] if boundary_position < len(items) else None for items in candidates]
        for start, end in _consistent_runs(series):
            for index in range(start, end):
                resolved[index] = series[index]
    return resolved


def pdf_page_labels(reader: object, page_count: int) -> list[str] | None:
    """Return labels only when the PDF explicitly contains a /PageLabels tree."""
    trailer = getattr(reader, "trailer", {})
    root = trailer.get("/Root", {}) if hasattr(trailer, "get") else {}
    root = root.get_object() if hasattr(root, "get_object") else root
    if not hasattr(root, "get") or root.get("/PageLabels") is None:
        return None
    labels = list(getattr(reader, "page_labels", []))
    return [str(label) for label in labels[:page_count]] if labels else None


def _boundary_candidates(text: str) -> list[str | None]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    boundary = [*lines[:2], *reversed(lines[-2:])]
    return [_label_from_line(line) for line in boundary]


def _label_from_line(line: str) -> str | None:
    tokens = line.split()
    for token in (*tokens[:1], *tokens[-1:]):
        cleaned = token.strip("|·•—–-()[]{}.,:;")
        if LABEL.fullmatch(cleaned):
            return cleaned
    return None


def _consistent_runs(labels: list[str | None]) -> list[tuple[int, int]]:
    runs: list[tuple[int, int]] = []
    start = 0
    while start < len(labels):
        if labels[start] is None:
            start += 1
            continue
        end = start + 1
        while end < len(labels) and labels[end] is not None and _successor(labels[end - 1] or "", labels[end] or ""):
            end += 1
        if end - start >= 2:
            runs.append((start, end))
        start = max(end, start + 1)
    return runs


def _successor(left: str, right: str) -> bool:
    if left.isdigit() and right.isdigit():
        return int(right) == int(left) + 1
    if re.fullmatch(r"[ivxlcdm]+", left, re.I) and re.fullmatch(r"[ivxlcdm]+", right, re.I):
        return _roman_value(right) == _roman_value(left) + 1
    left_match = re.fullmatch(r"([^\W\d_]{1,8})[-–](\d{1,5})", left, re.I)
    right_match = re.fullmatch(r"([^\W\d_]{1,8})[-–](\d{1,5})", right, re.I)
    return bool(
        left_match
        and right_match
        and left_match.group(1).casefold() == right_match.group(1).casefold()
        and int(right_match.group(2)) == int(left_match.group(2)) + 1
    )


def _roman_value(value: str) -> int:
    total = previous = 0
    for character in reversed(value.casefold()):
        current = ROMAN_VALUES[character]
        total += -current if current < previous else current
        previous = max(previous, current)
    return total
