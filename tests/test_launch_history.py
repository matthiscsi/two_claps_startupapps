import json

from src.launch_history import (
    append_launch_history,
    append_launch_history_many,
    clear_launch_history,
    format_launch_history,
    read_launch_history,
)


def test_append_and_read_launch_history_filters_and_limits(tmp_path):
    path = tmp_path / "launch_history.jsonl"
    append_launch_history(
        {"status": "success", "item": "News", "message": "opened", "item_type": "url", "target": "https://example.com"},
        routine="morning",
        source="test",
        dry_run=True,
        path=str(path),
    )
    append_launch_history(
        {"status": "skipped", "item": "Music", "message": "disabled"},
        routine="morning",
        source="test",
        path=str(path),
    )

    all_entries = read_launch_history(path=str(path), limit=10)
    assert [entry["item"] for entry in all_entries] == ["News", "Music"]
    assert all_entries[0]["dry_run"] is True

    skipped = read_launch_history(path=str(path), status="skipped")
    assert len(skipped) == 1
    assert skipped[0]["message"] == "disabled"

    assert read_launch_history(path=str(path), limit=1)[0]["item"] == "Music"


def test_launch_history_skips_malformed_lines_and_clears(tmp_path):
    path = tmp_path / "launch_history.jsonl"
    path.write_text('not-json\n{"status":"success","routine":"r","item":"A"}\n[]\n', encoding="utf-8")

    entries = read_launch_history(path=str(path))
    assert len(entries) == 1
    assert entries[0]["item"] == "A"

    clear_launch_history(path=str(path))
    assert read_launch_history(path=str(path)) == []


def test_append_many_and_format_history(tmp_path):
    path = tmp_path / "launch_history.jsonl"
    append_launch_history_many(
        [
            {"status": "success", "item": "One", "message": "ok"},
            {"status": "failure", "item": "Two", "message": "bad"},
        ],
        routine="work",
        source="unit",
        path=str(path),
    )
    raw = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert [entry["status"] for entry in raw] == ["success", "failure"]

    text = format_launch_history(read_launch_history(path=str(path)))
    assert "One" in text
    assert "failure" in text
