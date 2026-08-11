"""Safe file writes: temp file -> validate -> atomic replace (stdlib only).

Guards against interrupted writes leaving a half-written JSONL/JSON file
(previously a killed update_index run turned records.jsonl and
index_manifest.json into all-NUL files, forcing a full rebuild).

On any failure the temp file is removed and the previous file is untouched.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Callable


def atomic_write(
    path: Path,
    writer: Callable,
    validator: Callable | None = None,
) -> None:
    """Write `path` via a temp file in the same directory, then os.replace.

    writer: callable(file_handle) that writes the full content.
    validator: optional callable(tmp_path) that raises on invalid content.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(
        prefix=path.name + ".tmp-", suffix=".tmp", dir=str(path.parent)
    )
    tmp_path = Path(tmp)
    try:
        if path.exists():
            os.chmod(tmp, path.stat().st_mode)
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            writer(fh)
        if validator is not None:
            validator(tmp_path)
        os.replace(tmp_path, path)
    except BaseException:
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise


def atomic_write_json(path: Path, obj) -> None:
    def writer(fh):
        json.dump(obj, fh, ensure_ascii=False, indent=2)
        fh.write("\n")

    def validator(tmp):
        with open(tmp, "r", encoding="utf-8") as fh:
            json.load(fh)

    atomic_write(path, writer, validator)


def atomic_write_jsonl(path: Path, records: list) -> None:
    def writer(fh):
        for record in records:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")

    def validator(tmp):
        with open(tmp, "r", encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    json.loads(line)

    atomic_write(path, writer, validator)
