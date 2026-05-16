"""Font Bakery `googlefonts` profile gate.

Runs the strict Google Fonts conformance profile and fails on any FAIL or
ERROR result. Expected to fail until METADATA.pb + OFL.txt +
DESCRIPTION.en_us.html land alongside the TTFs — that is the intended
build gate.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from typing import Any

import pytest


def _walk_results(node: Any, out: list[dict]):
    """Recursively collect dicts that have a 'result' key from Font Bakery JSON."""
    if isinstance(node, dict):
        if "result" in node and isinstance(node.get("result"), str):
            out.append(node)
        for v in node.values():
            _walk_results(v, out)
    elif isinstance(node, list):
        for item in node:
            _walk_results(item, out)


def _run_fontbakery(family_paths, json_out, project_root):
    pytest.importorskip("fontbakery")
    if shutil.which("fontbakery") is None and not _module_available("fontbakery"):
        pytest.skip("fontbakery CLI not on PATH and module not importable")

    cmd = [
        sys.executable, "-m", "fontbakery", "check-googlefonts",
        *[str(p) for p in family_paths],
        "--json", str(json_out),
        "--loglevel", "FAIL",
        "--no-progress", "--no-colors",
    ]
    proc = subprocess.run(
        cmd,
        cwd=str(project_root),
        capture_output=True,
        text=True,
        timeout=600,
    )
    return proc


def _module_available(name):
    import importlib.util
    return importlib.util.find_spec(name) is not None


_SKIPPABLE_STDERR_MARKERS = (
    "No module named 'shaperglot'",
    "No module named 'glyphsets'",
    "Check 'googlefonts/glyphsets/shape_languages' not found",
)


def _collect_problems(json_path):
    if not json_path.exists():
        return [], "fontbakery did not produce a JSON report"
    data = json.loads(json_path.read_text(encoding="utf-8"))
    nodes: list[dict] = []
    _walk_results(data, nodes)
    problems = [
        {
            "key": n.get("key") or n.get("check_id") or "?",
            "result": n["result"],
            "message": (n.get("logs") or n.get("message") or [None])[0] if isinstance(n.get("logs"), list) else n.get("message"),
        }
        for n in nodes if n["result"] in {"FAIL", "ERROR"}
    ]
    return problems, None


def _run_and_check(family_paths, json_out, project_root, family_label):
    proc = _run_fontbakery(family_paths, json_out, project_root)
    if not json_out.exists():
        if any(m in proc.stderr for m in _SKIPPABLE_STDERR_MARKERS):
            pytest.skip(
                "fontbakery googlefonts profile cannot load on this host — missing "
                "optional dep (shaperglot/glyphsets). On Windows with Python 3.14 "
                "install Visual Studio Build Tools and re-run pip install, or use "
                "Python 3.13 where prebuilt wheels exist."
            )
        pytest.fail(
            f"fontbakery did not produce a JSON report\n"
            f"stdout:\n{proc.stdout[-2000:]}\nstderr:\n{proc.stderr[-2000:]}"
        )
    problems, _ = _collect_problems(json_out)
    assert not problems, _format_problems(family_label, problems)


@pytest.mark.fontbakery
def test_sans_fontbakery_googlefonts(sans_ttfs, tmp_path, project_root):
    _run_and_check(sans_ttfs, tmp_path / "fb-sans.json", project_root, "Sans")


@pytest.mark.fontbakery
def test_serif_fontbakery_googlefonts(serif_ttfs, tmp_path, project_root):
    _run_and_check(serif_ttfs, tmp_path / "fb-serif.json", project_root, "Serif")


def _format_problems(family, problems):
    lines = [f"{family}: {len(problems)} fontbakery FAIL/ERROR results"]
    for p in problems[:20]:
        lines.append(f"  [{p['result']}] {p['key']}: {p.get('message')}")
    if len(problems) > 20:
        lines.append(f"  … and {len(problems) - 20} more")
    return "\n".join(lines)
