"""Fontspector `googlefonts` profile gate.

Runs the strict Google Fonts conformance profile via the fontspector Rust
binary and fails on any FAIL, FATAL or ERROR result.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest


def _collect_problems(json_path: Path) -> list[dict]:
    data = json.loads(json_path.read_text(encoding="utf-8"))
    problems: list[dict] = []
    for _path, sections in data.get("results", {}).items():
        if not isinstance(sections, dict):
            continue
        for _section, checks in sections.items():
            for check in checks:
                if check.get("worst_status") in {"FAIL", "FATAL", "ERROR"}:
                    for sub in check.get("subresults", []):
                        if sub.get("severity") in {"FAIL", "FATAL", "ERROR"}:
                            problems.append({
                                "check_id": check["check_id"],
                                "severity": sub["severity"],
                                "message": sub.get("message", ""),
                            })
    return problems


def _run_and_check(family_paths: list[Path], json_out: Path, family_label: str):
    if shutil.which("fontspector") is None:
        pytest.skip("fontspector binary not on PATH — install from https://github.com/fonttools/fontspector/releases")

    cmd = [
        "fontspector",
        "--profile", "googlefonts",
        "--json", str(json_out),
        *[str(p) for p in family_paths],
    ]
    subprocess.run(cmd, capture_output=True, text=True, timeout=600)

    if not json_out.exists():
        pytest.fail(f"fontspector did not produce a JSON report for {family_label}")

    problems = _collect_problems(json_out)
    assert not problems, _format_problems(family_label, problems)


def _format_problems(family: str, problems: list[dict]) -> str:
    lines = [f"{family}: {len(problems)} fontspector FAIL/FATAL/ERROR results"]
    for p in problems[:20]:
        lines.append(f"  [{p['severity']}] {p['check_id']}: {p['message'][:200]}")
    if len(problems) > 20:
        lines.append(f"  … and {len(problems) - 20} more")
    return "\n".join(lines)


@pytest.mark.fontspector
def test_sans_fontspector_googlefonts(sans_ttfs, tmp_path, project_root):
    _run_and_check(sans_ttfs, tmp_path / "fs-sans.json", "Sans")


@pytest.mark.fontspector
def test_serif_fontspector_googlefonts(serif_ttfs, tmp_path, project_root):
    _run_and_check(serif_ttfs, tmp_path / "fs-serif.json", "Serif")
