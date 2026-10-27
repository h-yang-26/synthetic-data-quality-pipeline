"""Fictional input generator. Only random.random() is used (stable across Python versions)."""
import csv
import random
from datetime import date, timedelta

from dq_pipeline.io import INPUT_COLUMNS

ROWS = 60
NAMES = {
    "PUMP": ["Transfer pump", "Booster pump", "Dosing pump"],
    "VALVE": ["Ball valve", "Check valve", "Relief valve"],
    "SENSOR": ["Level sensor", "Flow sensor", "Temperature probe"],
    "MOTOR": ["Drive motor", "Fan motor", "Servo motor"],
    "FILTER": ["Inlet filter", "Oil filter", "Air filter"],
}
CATEGORIES = sorted(NAMES)
ALIASES = {"PUMP": ["pmp", "centrifugal pump"], "VALVE": ["vlv", "gate valve"],
           "SENSOR": ["temp sensor"], "MOTOR": ["mtr", "electric motor"], "FILTER": ["flt", "filter element"]}
MAPPING_ROWS = [(a, c) for c in CATEGORIES for a in ALIASES[c]] + [("pressure unit", "PUMP"), ("pressure unit", "SENSOR")]
# defect kind -> how many rows get it
DEFECTS = [("missing_id", 2), ("duplicate_id", 2), ("ambiguous", 3), ("unknown", 3), ("blank_qty", 2),
           ("zero_qty", 3), ("decimal_qty", 1), ("negative_qty", 1), ("text_qty", 1), ("slash_date", 2),
           ("blank_date", 1), ("bad_calendar_date", 1), ("blank_name", 1), ("blank_category", 1)]


def _pick(rng, seq):
    return seq[int(rng.random() * len(seq))]


def generate_rows(seed=42, n=ROWS):
    rng = random.Random(seed)
    order = sorted(range(n), key=lambda i: (rng.random(), i))
    kind_at, pos = {}, 0
    for kind, count in DEFECTS:
        for _ in range(count):
            kind_at[order[pos]] = kind
            pos += 1
    base = date(2024, 1, 1)
    rows = []
    for i in range(n):
        cat = _pick(rng, CATEGORIES)
        if rng.random() < 0.4:
            cat_text = _pick(rng, ALIASES[cat])
        else:
            cat_text = cat if rng.random() < 0.5 else cat.lower()
        if rng.random() < 0.2:
            cat_text = f"  {cat_text} "
        row = {
            "record_id": f"EQ-{i + 1:04d}",
            "category": cat_text,
            "item_name": _pick(rng, NAMES[cat]) + (" " * int(rng.random() * 3)),
            "quantity": str(1 + int(rng.random() * 200)),
            "received_date": (base + timedelta(days=int(rng.random() * 365))).isoformat(),
        }
        kind = kind_at.get(i)
        if kind == "missing_id":
            row["record_id"] = ""
        elif kind == "duplicate_id" and rows:
            row["record_id"] = " " + _pick(rng, rows)["record_id"]
        elif kind == "ambiguous":
            row["category"] = "Pressure Unit"
        elif kind == "unknown":
            row["category"] = _pick(rng, ["gizmo", "thermal blanket", "widget"])
        elif kind == "blank_qty":
            row["quantity"] = ""
        elif kind == "zero_qty":
            row["quantity"] = "0"
        elif kind == "decimal_qty":
            row["quantity"] = "12.5"
        elif kind == "negative_qty":
            row["quantity"] = "-4"
        elif kind == "text_qty":
            row["quantity"] = "N/A"
        elif kind == "slash_date":
            row["received_date"] = "03/04/2024"
        elif kind == "blank_date":
            row["received_date"] = ""
        elif kind == "bad_calendar_date":
            row["received_date"] = "2024-02-30"
        elif kind == "blank_name":
            row["item_name"] = "  "
        elif kind == "blank_category":
            row["category"] = ""
        rows.append(row)
    return rows


def write_sample(input_path, mapping_path, seed=42):
    with open(input_path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=INPUT_COLUMNS, lineterminator="\n")
        w.writeheader()
        w.writerows(generate_rows(seed))
    with open(mapping_path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["alias", "product_category"])
        w.writerows(MAPPING_ROWS)
