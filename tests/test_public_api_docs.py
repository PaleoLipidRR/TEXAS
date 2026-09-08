"""The published surface of TEXAS: it resolves, it is used, it is documented.

Three properties, each of which has failed silently in this package before:

1. A name in ``__all__`` that does not resolve is an ImportError for anyone
   doing ``from TEXAS import *``.
2. A name nothing calls is dead weight on the public API. The 2026-09-07 audit
   found six such helpers and deleted them; this stops the next six accruing.
3. A one-line docstring on a fifteen-argument function is not documentation.
   Three lines is a low bar deliberately -- ruff's D1 rules enforce *presence*,
   this enforces that presence means something.

Reference scanning looks at code cells only, so a name that appears in a
notebook's stored *output* does not count, and this file excludes itself, so a
name cannot be kept alive by being listed here.
"""
import inspect
import json
import re
from pathlib import Path

import pytest

import TEXAS

REPO = Path(__file__).resolve().parents[1]
SELF = Path(__file__).resolve()
MIN_DOC_LINES = 3


def _python_sources() -> list[str]:
    """Every test module except this one, plus every notebook code cell."""
    chunks = []
    for path in sorted((REPO / "tests").rglob("*.py")):
        if path.resolve() == SELF:
            continue
        chunks.append(path.read_text(encoding="utf-8", errors="replace"))
    for path in sorted((REPO / "notebooks").rglob("*.ipynb")):
        if ".ipynb_checkpoints" in path.parts:
            continue
        try:
            nb = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        except (json.JSONDecodeError, OSError):
            continue
        for cell in nb.get("cells", []):
            if cell.get("cell_type") == "code":
                chunks.append("".join(cell.get("source", [])))
    return chunks


SOURCES = _python_sources()


@pytest.mark.parametrize("name", TEXAS.__all__)
def test_export_resolves(name):
    """`from TEXAS import *` must not raise."""
    assert hasattr(TEXAS, name), f"TEXAS.__all__ lists '{name}' but it does not resolve"


@pytest.mark.parametrize("name", TEXAS.__all__)
def test_export_is_referenced(name):
    """Something must use it, or it should not be exported.

    If this fails on a name you just added, write a test that calls it. If you
    cannot think of one, that is the finding.
    """
    if name == "__version__":
        pytest.skip("module dunder, exercised by test_imports.py")
    pattern = re.compile(rf"\b{re.escape(name)}\b")
    assert any(pattern.search(chunk) for chunk in SOURCES), (
        f"'{name}' is exported from TEXAS but no test module or notebook code "
        f"cell references it. Add a test that calls it, or drop it from "
        f"__all__ and add a CHANGELOG line."
    )


@pytest.mark.parametrize("name", TEXAS.__all__)
def test_export_is_documented(name):
    """Functions and classes need a docstring with something in it."""
    obj = getattr(TEXAS, name)
    if not (inspect.isfunction(obj) or inspect.isclass(obj)):
        pytest.skip(f"'{name}' is a constant or registry, not a callable")
    doc = (inspect.getdoc(obj) or "").strip()
    n_lines = len(doc.splitlines())
    assert n_lines >= MIN_DOC_LINES, (
        f"'{name}' has a {n_lines}-line docstring. The standard is a one-line "
        f"summary, then Args/Returns (and Raises where it raises); see the "
        f"other exports for the shape."
    )


def test_the_scan_can_actually_fail():
    """A canary: if _python_sources() ever returns nothing, every check above
    would pass vacuously except test_export_is_referenced, which would fail
    everywhere. Assert the corpus is real."""
    assert len(SOURCES) > 20, "the reference corpus looks empty; the scan is broken"
    assert any("predict_T_from_proxyObs" in chunk for chunk in SOURCES)
