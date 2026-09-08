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


# ── pyproject dependency-audit guards (spec §9.2) ─────────────────────────────
# Each of these encodes a finding from the 2026-09-07 dependency audit. They are
# tests rather than comments because a dependency list drifts silently.

try:
    import tomllib                      # Python 3.11+
except ModuleNotFoundError:             # pragma: no cover - environment.yml pins python=3.10
    tomllib = None

# CI runs 3.11/3.12 so these always execute there; the conda env is 3.10.
needs_tomllib = pytest.mark.skipif(tomllib is None,
                                   reason="tomllib requires Python 3.11+")


def _pyproject() -> dict:
    return tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))


@needs_tomllib
def test_core_deps_do_not_include_packages_the_package_never_imports():
    """cmocean and plotly are notebook/Streamlit deps, not core runtime deps."""
    core = " ".join(_pyproject()["project"]["dependencies"])
    assert "cmocean" not in core, "cmocean belongs in the `plotting` extra"
    assert "plotly" not in core, (
        "plotly is used only by streamlit_app/, which has its own "
        "requirements.streamlit.txt"
    )


@needs_tomllib
def test_plotting_extra_carries_cmocean():
    extras = _pyproject()["project"]["optional-dependencies"]
    assert any(d.startswith("cmocean") for d in extras["plotting"])


@needs_tomllib
def test_maps_extra_declares_joblib():
    """residual_maps.py imports joblib; it used to arrive via scikit-learn."""
    extras = _pyproject()["project"]["optional-dependencies"]
    assert any(d.startswith("joblib") for d in extras["maps"])


def _req_name(dep: str) -> str:
    """Bare distribution name from a PEP 508 requirement string.

    Splits on every character that can legally follow the name -- version
    operators, an extras bracket, an environment marker, whitespace -- so a
    banned package cannot slip back in under a spelling the guard fails to
    recognise (``statsmodels~=0.14``, ``pydantic[email]``,
    ``odrpack ; python_version<'3.13'``).
    """
    return re.split(r"[<>=!~;\[\s]", dep, maxsplit=1)[0].strip()


@needs_tomllib
def test_dev_extra_has_no_unreferenced_packages():
    """anywidget/ipylab/duckdb/sqlalchemy/pydantic/statsmodels/odrpack are unused."""
    dev = _pyproject()["project"]["optional-dependencies"]["dev"]
    names = {_req_name(d) for d in dev}
    for gone in ("anywidget", "ipylab", "duckdb", "sqlalchemy",
                 "pydantic", "statsmodels", "odrpack"):
        assert gone not in names, f"{gone} is back in the dev extra; nothing imports it"


@needs_tomllib
def test_dev_extra_keeps_the_implicit_pandas_backends():
    """pyarrow backs pd.read_parquet, openpyxl backs pd.read_excel."""
    dev = _pyproject()["project"]["optional-dependencies"]["dev"]
    names = {_req_name(d) for d in dev}
    assert "pyarrow" in names and "openpyxl" in names


@needs_tomllib
def test_regrid_extra_is_just_xesmf():
    """utils/regrid.py imports only xesmf (+ esmpy at runtime, conda-only)."""
    extras = _pyproject()["project"]["optional-dependencies"]
    assert extras["regrid"] == ["xesmf"], extras["regrid"]


def test_no_pyproj_pin_and_no_uv_override_to_undo_it():
    """The `pyproj<3.6` cap and the [tool.uv] override that undid it both go."""
    text = PYPROJECT.read_text(encoding="utf-8")
    assert "pyproj<3.6" not in text
    assert "override-dependencies" not in text, (
        "the only override-dependencies entry existed to undo pyproj<3.6"
    )


@needs_tomllib
def test_no_extra_lists_esmpy():
    """esmpy is not on PyPI; one non-PyPI package in any extra breaks `uv lock`."""
    extras = _pyproject()["project"]["optional-dependencies"]
    for name, deps in extras.items():
        assert not any(d.startswith("esmpy") for d in deps), f"esmpy in [{name}]"
