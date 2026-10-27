"""Deterministic category mapping from an exact (normalized) alias table."""
import csv

from dq_pipeline.errors import FatalError
from dq_pipeline.normalize import alias_key

PERMITTED_CATEGORIES = ("FILTER", "MOTOR", "PUMP", "SENSOR", "VALVE")
MAPPING_COLUMNS = ("alias", "product_category")


def load_mapping(path):
    """Return {alias_key: frozenset(targets)}. Canonical names map to themselves.

    An alias with more than one distinct target is ambiguous; it is kept as a
    multi-target entry so the pipeline can refuse to choose.
    """
    table = {alias_key(c): {c} for c in PERMITTED_CATEGORIES}
    try:
        with open(path, newline="", encoding="utf-8-sig") as fh:
            # Header names are trimmed (as for the input file), so fields are read by position.
            reader = csv.reader(fh)
            header = next(reader, None)
            if header is None or [c.strip() for c in header] != list(MAPPING_COLUMNS):
                raise FatalError(f"mapping file {path}: header must be {','.join(MAPPING_COLUMNS)}")
            for line_no, fields in enumerate(reader, start=2):
                if not fields:
                    continue
                if len(fields) != len(MAPPING_COLUMNS):
                    raise FatalError(f"mapping file {path} line {line_no}: expected {len(MAPPING_COLUMNS)} fields")
                alias, target = (f.strip() for f in fields)
                if not alias:
                    raise FatalError(f"mapping file {path} line {line_no}: empty alias")
                if target not in PERMITTED_CATEGORIES:
                    raise FatalError(f"mapping file {path} line {line_no}: target {target!r} is not a permitted category")
                table.setdefault(alias_key(alias), set()).add(target)
    except OSError as exc:
        raise FatalError(f"cannot read mapping file {path}: {exc}") from exc
    except UnicodeDecodeError as exc:
        raise FatalError(f"mapping file {path} is not valid UTF-8: {exc}") from exc
    return {k: frozenset(v) for k, v in table.items()}


def map_category(raw, table):
    """Return (targets, status); status is 'mapped', 'ambiguous' or 'unknown'.

    Exact match only. No fuzzy matching, so near-misses are 'unknown'.
    """
    targets = table.get(alias_key(raw))
    if targets is None:
        return frozenset(), "unknown"
    if len(targets) > 1:
        return targets, "ambiguous"
    return targets, "mapped"
