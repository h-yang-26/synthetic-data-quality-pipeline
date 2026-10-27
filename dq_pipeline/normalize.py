"""Superficial formatting normalization. Never changes business meaning."""


def collapse_ws(text):
    return " ".join(text.split())


def normalize_id(raw):
    """Trim only; case is significant, so 'eq-1' and 'EQ-1' are different IDs."""
    return raw.strip()


def normalize_name(raw):
    return collapse_ws(raw)


def alias_key(raw):
    """Lookup key for category text: whitespace-collapsed and case-folded."""
    return collapse_ws(raw).casefold()
