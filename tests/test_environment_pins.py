"""Guard the plotting pins in environment.yml.

`matplotlib<3.5` and `matplotlib-inline<0.2` were proplot's constraints
(proplot 0.9.7 caps matplotlib below 3.5). This project replaced proplot with
ultraplot in 2026-07, and ultraplot needs ``matplotlib>=3.9``. With the old cap
in place the solver cannot install ultraplot at all: it silently falls back to
ultraplot 1.0, which ``pyproject.toml`` forbids and which then fails to import
against matplotlib 3.4 (``matplotlib.cm.ColormapRegistry`` arrived in 3.5).

That produced a Docker image whose SI notebooks crashed on ``import
ultraplot`` -- and because they guard with ``except ImportError``, the
``AttributeError`` was not caught.

This has regressed twice: added in c7e70bf, fixed in 45234fd the same day, and
back again by 2026-08. Hence a test rather than a comment.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
ENV_YML = REPO / "environment.yml"
PYPROJECT = REPO / "pyproject.toml"

pytestmark = pytest.mark.skipif(
    not ENV_YML.exists(), reason="environment.yml not present (installed package)"
)


def _dep_lines() -> list[str]:
    return [ln.strip().lstrip("- ").strip()
            for ln in ENV_YML.read_text(encoding="utf-8").splitlines()
            if ln.strip().startswith("- ")]


def test_matplotlib_not_capped_below_ultraplot_floor():
    """No matplotlib cap under 3.9 -- that is the proplot-era pin."""
    for dep in _dep_lines():
        if not re.match(r"^matplotlib\b(?!-)", dep):
            continue
        for m in re.finditer(r"<=?\s*(\d+)\.(\d+)", dep):
            major, minor = int(m.group(1)), int(m.group(2))
            assert (major, minor) >= (3, 9), (
                f"environment.yml pins {dep!r}, which is below ultraplot's "
                "matplotlib>=3.9 floor. That is proplot's old constraint and it "
                "makes ultraplot uninstallable. See tests/test_environment_pins.py."
            )


def test_matplotlib_inline_not_pinned_below_1():
    """matplotlib-inline was capped only to satisfy the proplot stack."""
    for dep in _dep_lines():
        if dep.startswith("matplotlib-inline"):
            assert "<0.2" not in dep, (
                f"environment.yml pins {dep!r}; that cap came in with the "
                "proplot matplotlib<3.5 pin and was removed with it."
            )


def test_ultraplot_floor_matches_pyproject():
    """environment.yml must not allow an ultraplot older than pyproject does."""
    pins = [d for d in _dep_lines() if d.startswith("ultraplot")]
    assert pins, "ultraplot missing from environment.yml"
    assert ">=2.4.0" in pins[0], (
        f"environment.yml has {pins[0]!r}; pyproject requires ultraplot>=2.4.0. "
        "Unpinned, the solver picks ultraplot 1.0, which cannot import."
    )
    assert "ultraplot>=2.4.0" in PYPROJECT.read_text(encoding="utf-8"), (
        "pyproject no longer requires ultraplot>=2.4.0 -- update this test and "
        "environment.yml together."
    )


def test_proplot_is_gone():
    assert not any(d.startswith("proplot") for d in _dep_lines()), (
        "proplot is back in environment.yml; it was superseded by ultraplot "
        "in 6eca051 and its matplotlib<3.5 requirement breaks the stack."
    )
