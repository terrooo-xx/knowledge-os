"""Atomic write tests: temp file -> validate -> atomic replace."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rag_engine.atomic_io import atomic_write, atomic_write_json, atomic_write_jsonl


def _tmp_files(dirpath: Path) -> list:
    return [p.name for p in dirpath.iterdir()]


def test_atomic_write_success():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        target = root / "out.jsonl"
        target.write_text("old\n", encoding="utf-8")
        atomic_write(target, lambda fh: fh.write("new\n"))
        assert target.read_text(encoding="utf-8") == "new\n"
        assert not any("tmp-" in n for n in _tmp_files(root))


def test_atomic_write_keeps_old_on_exception():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        target = root / "out.jsonl"
        target.write_text("old\n", encoding="utf-8")

        def bad_writer(fh):
            fh.write("partial")
            raise RuntimeError("boom")

        try:
            atomic_write(target, bad_writer)
        except RuntimeError:
            pass
        else:
            raise AssertionError("exception not raised")
        assert target.read_text(encoding="utf-8") == "old\n"
        assert not any("tmp-" in n for n in _tmp_files(root))


def test_atomic_write_json_validation_failure():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        target = root / "manifest.json"
        target.write_text('{"old": true}\n', encoding="utf-8")

        def bad_validator(tp):
            raise ValueError("invalid json")

        try:
            atomic_write(target, lambda fh: fh.write("{not json"), bad_validator)
        except ValueError:
            pass
        else:
            raise AssertionError("validator error not raised")
        assert json.loads(target.read_text(encoding="utf-8")) == {"old": True}
        assert not any("tmp-" in n for n in _tmp_files(root))


def test_atomic_write_jsonl_roundtrip():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        target = root / "records.jsonl"
        atomic_write_jsonl(target, [{"id": "1"}, {"id": "2"}])
        lines = [json.loads(ln) for ln in target.read_text(encoding="utf-8").splitlines()]
        assert [r["id"] for r in lines] == ["1", "2"]


def test_atomic_write_json_roundtrip():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        target = root / "manifest.json"
        atomic_write_json(target, {"doc": {"hash": "h", "chunks": 2}})
        assert json.loads(target.read_text(encoding="utf-8"))["doc"]["chunks"] == 2


if __name__ == "__main__":
    for t in (
        test_atomic_write_success,
        test_atomic_write_keeps_old_on_exception,
        test_atomic_write_json_validation_failure,
        test_atomic_write_jsonl_roundtrip,
        test_atomic_write_json_roundtrip,
    ):
        t()
        print(f"PASS {t.__name__}")
    print("all atomic write tests passed")
