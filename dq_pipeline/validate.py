"""Row validation. Returns accepted records or error lists; never guesses."""
import re
from datetime import date

from dq_pipeline import errors as E
from dq_pipeline.mapping import map_category
from dq_pipeline.normalize import normalize_id, normalize_name

# [0-9], not \d: \d also matches non-ASCII digits such as Arabic-Indic or fullwidth.
_ISO = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
_DIGITS = re.compile(r"[0-9]+")


def parse_quantity(raw):
    """Return (int|None, error|None). Blank is missing; '0' is a valid zero."""
    text = raw.strip()
    if not text:
        return None, (E.MISSING_QUANTITY, "quantity is blank")
    if not _DIGITS.fullmatch(text):
        return None, (E.INVALID_QUANTITY, f"quantity {text!r} is not a nonnegative whole number")
    return int(text), None


def parse_date(raw):
    """Accept only ISO YYYY-MM-DD that is a real calendar date."""
    text = raw.strip()
    if not text:
        return None, (E.MISSING_DATE, "received_date is blank")
    if not _ISO.fullmatch(text):
        return None, (E.INVALID_DATE, f"received_date {text!r} is not YYYY-MM-DD (other formats are not guessed)")
    try:
        date(int(text[:4]), int(text[5:7]), int(text[8:]))
    except ValueError:
        return None, (E.INVALID_DATE, f"received_date {text!r} is not a real calendar date")
    return text, None


def duplicate_ids(rows):
    """Normalized IDs that occur on more than one row."""
    counts = {}
    for row in rows:
        rid = normalize_id(row.raw["record_id"])
        if rid:
            counts[rid] = counts.get(rid, 0) + 1
    return {rid for rid, n in counts.items() if n > 1}


def validate_row(row, mapping, dup_ids):
    """Return (record|None, [(code, message), ...]); exactly one of them is non-empty."""
    errs = []
    raw = row.raw
    if row.malformed:
        errs.append((E.MALFORMED_ROW, "row has a different number of fields than the header"))

    record_id = normalize_id(raw["record_id"])
    if not record_id:
        errs.append((E.MISSING_ID, "record_id is blank"))
    elif record_id in dup_ids:
        errs.append((E.DUPLICATE_ID, f"record_id {record_id!r} appears on more than one row"))

    category = None
    if not raw["category"].strip():
        errs.append((E.MISSING_CATEGORY, "category is blank"))
    else:
        targets, status = map_category(raw["category"], mapping)
        if status == "unknown":
            errs.append((E.UNKNOWN_CATEGORY, f"category {raw['category'].strip()!r} has no mapping"))
        elif status == "ambiguous":
            errs.append((E.AMBIGUOUS_CATEGORY,
                         f"category {raw['category'].strip()!r} maps to several targets: {', '.join(sorted(targets))}"))
        else:
            (category,) = targets

    item_name = normalize_name(raw["item_name"])
    if not item_name:
        errs.append((E.MISSING_ITEM_NAME, "item_name is blank"))

    quantity, err = parse_quantity(raw["quantity"])
    if err:
        errs.append(err)
    received, err = parse_date(raw["received_date"])
    if err:
        errs.append(err)

    if errs:
        return None, errs
    return {
        "source_row_number": row.number,
        "record_id": record_id,
        "product_category": category,
        "item_name": item_name,
        "quantity": quantity,
        "received_date": received,
    }, []
