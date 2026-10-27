"""Reading the source CSV and writing outputs (files are replaced each run)."""
import csv
import json
from dataclasses import dataclass
from pathlib import Path

from dq_pipeline.errors import FatalError

INPUT_COLUMNS = ("record_id", "category", "item_name", "quantity", "received_date")
CLEAN_COLUMNS = ("source_row_number", "record_id", "product_category", "item_name", "quantity", "received_date")
EXCEPTION_COLUMNS = ("source_row_number", "raw_record_id", "raw_category", "raw_item_name",
                     "raw_quantity", "raw_received_date", "error_codes", "error_messages")


@dataclass
class SourceRow:
    number: int          # 1-based data-row index, independent of the business ID
    raw: dict            # raw field values keyed by INPUT_COLUMNS (untrimmed)
    malformed: bool = False


def read_source(path):
    """Read rows. Completely empty lines are skipped and not counted as rows."""
    try:
        with open(path, newline="", encoding="utf-8-sig") as fh:
            reader = csv.reader(fh)
            header = next(reader, None)
            if header is None:
                raise FatalError(f"input file {path} is empty")
            header = [h.strip() for h in header]
            duplicates = sorted(c for c in set(header) if header.count(c) > 1)
            if duplicates:
                raise FatalError(f"input file {path}: duplicate columns: {', '.join(duplicates)}")
            missing = [c for c in INPUT_COLUMNS if c not in header]
            if missing:
                raise FatalError(f"input file {path}: missing required columns: {', '.join(missing)}")
            idx = {c: header.index(c) for c in INPUT_COLUMNS}
            rows, number = [], 0
            for fields in reader:
                if not fields:
                    continue
                number += 1
                malformed = len(fields) != len(header)
                raw = {c: fields[i] if i < len(fields) else "" for c, i in idx.items()}
                rows.append(SourceRow(number, raw, malformed))
            return rows
    except OSError as exc:
        raise FatalError(f"cannot read input file {path}: {exc}") from exc
    except UnicodeDecodeError as exc:
        raise FatalError(f"input file {path} is not valid UTF-8: {exc}") from exc


def _write_csv(path, columns, records):
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(records)


def write_outputs(out_dir, cleaned, exceptions, summary):
    out_dir = Path(out_dir)
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        _write_csv(out_dir / "cleaned_records.csv", CLEAN_COLUMNS, cleaned)
        _write_csv(out_dir / "exceptions.csv", EXCEPTION_COLUMNS, exceptions)
        (out_dir / "summary.json").write_text(
            json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    except OSError as exc:
        raise FatalError(f"cannot write outputs to {out_dir}: {exc}") from exc
