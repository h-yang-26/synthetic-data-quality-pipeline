"""Orchestration: read -> normalize/map -> validate -> accepted OR exception."""
from pathlib import Path

from dq_pipeline.io import read_source, write_outputs
from dq_pipeline.mapping import load_mapping
from dq_pipeline.validate import duplicate_ids, validate_row


def process(rows, mapping):
    """Pure computation: returns (cleaned, exceptions, summary_without_file_names)."""
    dups = duplicate_ids(rows)
    cleaned, exceptions = [], []
    issues_by_code, rows_by_code, by_category = {}, {}, {}
    for row in rows:
        record, errs = validate_row(row, mapping, dups)
        if record:
            cleaned.append(record)
            by_category[record["product_category"]] = by_category.get(record["product_category"], 0) + 1
            continue
        for code, _ in errs:
            issues_by_code[code] = issues_by_code.get(code, 0) + 1
        for code in {c for c, _ in errs}:
            rows_by_code[code] = rows_by_code.get(code, 0) + 1
        raw = row.raw
        exceptions.append({
            "source_row_number": row.number,
            "raw_record_id": raw["record_id"],
            "raw_category": raw["category"],
            "raw_item_name": raw["item_name"],
            "raw_quantity": raw["quantity"],
            "raw_received_date": raw["received_date"],
            "error_codes": ";".join(c for c, _ in errs),
            "error_messages": " | ".join(m for _, m in errs),
        })
    summary = {
        "input_rows": len(rows),
        "accepted_rows": len(cleaned),
        "rejected_rows": len(exceptions),
        "issue_count": sum(issues_by_code.values()),
        "reconciled": len(rows) == len(cleaned) + len(exceptions),
        "issues_by_code": dict(sorted(issues_by_code.items())),
        "rejected_rows_by_code": dict(sorted(rows_by_code.items())),
        "accepted_by_category": dict(sorted(by_category.items())),
    }
    return cleaned, exceptions, summary


def run(input_path, mapping_path, out_dir):
    """Run end to end. Raises FatalError before writing anything if inputs are unusable."""
    mapping = load_mapping(mapping_path)
    rows = read_source(input_path)
    cleaned, exceptions, summary = process(rows, mapping)
    summary = {"input_file": Path(input_path).name, "mapping_file": Path(mapping_path).name, **summary}
    write_outputs(out_dir, cleaned, exceptions, summary)
    return summary
