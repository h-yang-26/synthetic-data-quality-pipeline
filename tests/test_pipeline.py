"""Tests. The mini fixture's expected values below were worked out by hand from
tests/fixtures/mini_input.csv, not produced by running the pipeline."""
import csv
import json
from pathlib import Path

import pytest

from dq_pipeline.cli import main
from dq_pipeline.generate import generate_rows, write_sample
from dq_pipeline.pipeline import run

FIX = Path(__file__).parent / "fixtures"
INPUT, MAPPING = FIX / "mini_input.csv", FIX / "mini_mapping.csv"
ROOT = Path(__file__).parent.parent


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


@pytest.fixture
def result(tmp_path):
    summary = run(INPUT, MAPPING, tmp_path)
    return summary, read_csv(tmp_path / "cleaned_records.csv"), read_csv(tmp_path / "exceptions.csv")


def codes(exceptions):
    return {int(e["source_row_number"]): e["error_codes"] for e in exceptions}


def test_accepted_rows_are_exactly_the_hand_checked_ones(result):
    _, cleaned, _ = result
    assert cleaned == [
        {"source_row_number": "1", "record_id": "A-1", "product_category": "PUMP",
         "item_name": "Pump A", "quantity": "5", "received_date": "2024-03-01"},
        # alias 'pmp' mapped, name whitespace collapsed, explicit zero kept, date trimmed
        {"source_row_number": "2", "record_id": "A-2", "product_category": "PUMP",
         "item_name": "Pump B", "quantity": "0", "received_date": "2024-03-02"},
        {"source_row_number": "11", "record_id": "A-11", "product_category": "MOTOR",
         "item_name": "Motor I", "quantity": "7", "received_date": "2024-03-11"},
    ]


def test_rejected_rows_and_codes(result):
    _, _, exceptions = result
    assert codes(exceptions) == {
        3: "MISSING_QUANTITY", 4: "MISSING_ID", 5: "DUPLICATE_ID", 6: "DUPLICATE_ID",
        7: "UNKNOWN_CATEGORY", 8: "AMBIGUOUS_CATEGORY", 9: "INVALID_QUANTITY",
        10: "INVALID_DATE", 12: "INVALID_QUANTITY;MISSING_DATE",
    }


def test_missing_quantity_is_not_zero(result):
    _, cleaned, exceptions = result
    assert "3" not in {r["source_row_number"] for r in cleaned}
    assert codes(exceptions)[3] == "MISSING_QUANTITY"
    assert next(r for r in cleaned if r["source_row_number"] == "2")["quantity"] == "0"


def test_duplicate_flags_every_occurrence_and_preserves_raw_id(result):
    _, _, exceptions = result
    rows = {int(e["source_row_number"]): e for e in exceptions}
    assert rows[5]["raw_record_id"] == "A-5"
    assert rows[6]["raw_record_id"] == " A-5 "  # raw value preserved untrimmed


def test_ambiguous_alias_is_not_guessed(result):
    _, cleaned, exceptions = result
    row = next(e for e in exceptions if e["source_row_number"] == "8")
    assert "PUMP, SENSOR" in row["error_messages"]
    assert all(r["record_id"] != "A-8" for r in cleaned)


def test_slash_date_not_interpreted(result):
    _, _, exceptions = result
    row = next(e for e in exceptions if e["source_row_number"] == "10")
    assert row["raw_received_date"] == "04/03/2024"
    assert "not guessed" in row["error_messages"]


def test_summary_counts_reconcile(result):
    summary, cleaned, exceptions = result
    assert (summary["input_rows"], summary["accepted_rows"], summary["rejected_rows"]) == (12, 3, 9)
    assert summary["issue_count"] == 10  # row 12 has two issues, so issues != rejected rows
    assert summary["reconciled"] is True
    seen = [int(r["source_row_number"]) for r in cleaned] + [int(e["source_row_number"]) for e in exceptions]
    assert sorted(seen) == list(range(1, 13))


def test_repeatable_and_outputs_are_replaced(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    run(INPUT, MAPPING, a)
    run(INPUT, MAPPING, b)
    run(INPUT, MAPPING, b)  # second run into same dir must replace, not append
    for name in ("cleaned_records.csv", "exceptions.csv", "summary.json"):
        assert (a / name).read_bytes() == (b / name).read_bytes()


def test_each_unusual_quantity():
    from dq_pipeline.validate import parse_quantity
    assert parse_quantity("0")[0] == 0
    assert parse_quantity(" 12 ")[0] == 12
    for bad in ("1.0", "-1", "+3", "1e3", "N/A", "٣"):
        assert parse_quantity(bad)[1][0] == "INVALID_QUANTITY"
    assert parse_quantity("  ")[1][0] == "MISSING_QUANTITY"


def test_fatal_errors_exit_2_and_write_nothing(tmp_path, capsys):
    out = tmp_path / "out"
    assert main(["run", "--input", str(tmp_path / "nope.csv"), "--mapping", str(MAPPING), "--output-dir", str(out)]) == 2
    bad = tmp_path / "bad.csv"
    bad.write_text("record_id,category\nA,B\n", encoding="utf-8")
    assert main(["run", "--input", str(bad), "--mapping", str(MAPPING), "--output-dir", str(out)]) == 2
    badmap = tmp_path / "map.csv"
    badmap.write_text("alias,product_category\nfoo,TOASTER\n", encoding="utf-8")
    assert main(["run", "--input", str(INPUT), "--mapping", str(badmap), "--output-dir", str(out)]) == 2
    assert not out.exists()
    assert "fatal:" in capsys.readouterr().err


def test_exceptions_present_still_exit_0(tmp_path):
    assert main(["run", "--input", str(INPUT), "--mapping", str(MAPPING), "--output-dir", str(tmp_path)]) == 0


@pytest.mark.parametrize("column", ["record_id", "quantity", "received_date"])
def test_duplicate_input_header_is_fatal_even_after_trimming(tmp_path, capsys, column):
    # Choosing either duplicate silently could change an ID, quantity, or date.
    src = tmp_path / "duplicate.csv"
    src.write_text(
        f"record_id,category,item_name,quantity,received_date, {column} \n"
        "A,pump,Pump,1,2024-01-01,conflicting-value\n", encoding="utf-8")
    out = tmp_path / "out"
    assert main(["run", "--input", str(src), "--mapping", str(MAPPING), "--output-dir", str(out)]) == 2
    assert not out.exists()
    assert f"duplicate columns: {column}" in capsys.readouterr().err


def test_malformed_row_is_an_exception(tmp_path):
    src = tmp_path / "in.csv"
    src.write_text("record_id,category,item_name,quantity,received_date\nA-1,pump,P,1\n", encoding="utf-8")
    summary = run(src, MAPPING, tmp_path / "o")
    assert summary["rejected_rows"] == 1
    assert "MALFORMED_ROW" in read_csv(tmp_path / "o" / "exceptions.csv")[0]["error_codes"]


def test_generator_is_seeded_and_committed_sample_matches(tmp_path):
    assert generate_rows(42) == generate_rows(42)
    assert generate_rows(42) != generate_rows(7)
    write_sample(tmp_path / "i.csv", tmp_path / "m.csv", 42)
    assert (tmp_path / "i.csv").read_bytes() == (ROOT / "data" / "sample_input.csv").read_bytes()
    assert (tmp_path / "m.csv").read_bytes() == (ROOT / "data" / "reference_mapping.csv").read_bytes()


def test_sample_output_reconciles_and_has_each_defect_class(tmp_path):
    summary = run(ROOT / "data" / "sample_input.csv", ROOT / "data" / "reference_mapping.csv", tmp_path)
    assert 40 <= summary["input_rows"] <= 80
    assert summary["accepted_rows"] + summary["rejected_rows"] == summary["input_rows"]
    for code in ("AMBIGUOUS_CATEGORY", "UNKNOWN_CATEGORY", "MISSING_QUANTITY", "MISSING_ID",
                 "DUPLICATE_ID", "INVALID_DATE"):
        assert code in summary["issues_by_code"]
    assert any(r["quantity"] == "0" for r in read_csv(tmp_path / "cleaned_records.csv"))
    assert json.loads((tmp_path / "summary.json").read_text())["reconciled"] is True


HEADER = "record_id,category,item_name,quantity,received_date\n"


def test_non_ascii_date_digits_rejected_through_pipeline(tmp_path):
    # Arabic-Indic and fullwidth digits form a real date if read as digits; the
    # contract allows only ASCII YYYY-MM-DD, so both rows must be rejected.
    arabic, fullwidth = "٢٠٢٤-٠٢-٢٩", "２０２４-０３-０１"
    src = tmp_path / "in.csv"
    src.write_text(HEADER + f"A-1,pump,P,1,{arabic}\nA-2,pump,P,1,{fullwidth}\nA-3,pump,P,1,2024-02-29\n",
                   encoding="utf-8")
    summary = run(src, MAPPING, tmp_path / "o")
    cleaned = read_csv(tmp_path / "o" / "cleaned_records.csv")
    exceptions = read_csv(tmp_path / "o" / "exceptions.csv")
    assert [r["record_id"] for r in cleaned] == ["A-3"]
    assert [(e["source_row_number"], e["error_codes"], e["raw_received_date"]) for e in exceptions] == [
        ("1", "INVALID_DATE", arabic), ("2", "INVALID_DATE", fullwidth)]
    assert summary["reconciled"] is True


def test_non_ascii_quantity_digits_rejected_through_pipeline(tmp_path):
    src = tmp_path / "in.csv"
    src.write_text(HEADER + "A-1,pump,P,٣,2024-03-01\nA-2,pump,P,５,2024-03-01\n", encoding="utf-8")
    run(src, MAPPING, tmp_path / "o")
    exceptions = read_csv(tmp_path / "o" / "exceptions.csv")
    assert [(e["error_codes"], e["raw_quantity"]) for e in exceptions] == [
        ("INVALID_QUANTITY", "٣"), ("INVALID_QUANTITY", "５")]


def test_padded_mapping_header_is_normalized_via_cli(tmp_path):
    # Header names are trimmed, as for the input file; the mapping rows must still apply.
    padded = tmp_path / "map.csv"
    padded.write_text(" alias , product_category \npmp,PUMP\n", encoding="utf-8")
    src = tmp_path / "in.csv"
    src.write_text(HEADER + "A-1,pmp,P,1,2024-03-01\n", encoding="utf-8")
    out = tmp_path / "o"
    assert main(["run", "--input", str(src), "--mapping", str(padded), "--output-dir", str(out)]) == 0
    assert read_csv(out / "cleaned_records.csv")[0]["product_category"] == "PUMP"


def test_mapping_row_with_wrong_field_count_is_fatal(tmp_path):
    bad = tmp_path / "map.csv"
    bad.write_text("alias,product_category\npmp,PUMP,extra\n", encoding="utf-8")
    out = tmp_path / "o"
    assert main(["run", "--input", str(INPUT), "--mapping", str(bad), "--output-dir", str(out)]) == 2
    assert not out.exists()
