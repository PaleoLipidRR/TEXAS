"""
The Streamlit app's parameter vocabulary must track the models.

Both failures this guards against are silent. `_compute_curves` required
`Q_crtp`, removed from every Stan model on 2026-03-24, so the check failed for
every posterior produced since and the function returned `{}` -- the calibration
envelope simply stopped drawing, with no error. And `PARAM_LABELS` still named
`sigma_scaledRI_crtp` after the rename to `sigma_proxyObs_crtp`, while
bounded-T's gamma pair was never added, so those three were displayed as raw
variable names.

Neither shows up as a crash, which is why a test is the only thing that catches
them.
"""
import ast
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
PAGE = REPO / "streamlit_app" / "pages" / "calibration_data.py"
STAN_DIR = REPO / "src" / "TEXAS" / "stan_models"
# The additive (beta-on-mu) model was archived in 2026-09, but its posteriors are
# still downloadable via `TEXAS.download_posteriors()`, so the app still has to
# label `beta_G23_crtp` / `beta_NO3_crtp`. Scan that archive too.
#
# Only that one. `stan_models/archive/` and `archive_pre_annotated/` predate the
# initial submission and still declare `Q_crtp` and `sigma_scaledRI_crtp` -- the
# exact two regressions this file exists to catch. Including them would let a
# genuinely dead label pass.
ARCHIVE_DIR = REPO / "archive" / "submission-2026-04" / "stan_models"

pytestmark = pytest.mark.skipif(not PAGE.exists(),
                                reason="streamlit app not present")


def _module_dict(name: str) -> dict:
    """Read a top-level dict literal out of the page without importing it."""
    tree = ast.parse(PAGE.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == name:
                    return ast.literal_eval(node.value)
    raise AssertionError(f"{name} not found in {PAGE.name}")


def _stan_sources() -> str:
    return "\n".join(p.read_text(encoding="utf-8", errors="replace")
                     for d in (STAN_DIR, ARCHIVE_DIR)
                     for p in sorted(d.glob("*.stan")))


def test_no_label_names_a_parameter_no_model_declares():
    """A dead entry never matches, so the UI quietly shows the raw name."""
    stan = _stan_sources()
    dead = [name for name in _module_dict("PARAM_LABELS")
            if not re.search(rf"\b{re.escape(name)}\b", stan)]
    assert not dead, (
        f"PARAM_LABELS names parameters no Stan model declares: {dead}. "
        "Q was removed on 2026-03-24 and sigma_scaledRI_crtp was renamed.")


def test_both_slope_conventions_are_labelled():
    """
    beta and gamma are different quantities in different units. Missing either
    means that model's two hardest-to-read parameters appear untranslated.
    """
    labels = _module_dict("PARAM_LABELS")
    for name in ("beta_G23_crtp", "beta_NO3_crtp",
                 "gamma_G23_crtp", "gamma_NO3_crtp"):
        assert name in labels, f"{name} has no human-readable label"


def test_curve_requirements_are_all_real_parameters():
    """
    The envelope silently stops drawing if `required` names something the
    posteriors no longer carry.
    """
    src = PAGE.read_text(encoding="utf-8")
    m = re.search(r"required\s*=\s*(\[[^\]]*\])", src)
    assert m, "could not find the `required` list in _compute_curves"
    stan = _stan_sources()
    missing = [p for p in ast.literal_eval(m.group(1))
               if not re.search(rf"\b{re.escape(p)}\b", stan)]
    assert not missing, (
        f"_compute_curves requires parameters no model declares: {missing}. "
        "The check would fail for every posterior and return {} silently.")


def test_the_page_uses_the_package_curve_not_a_copy():
    """A local copy of the curve is how this page drifted out of step."""
    src = PAGE.read_text(encoding="utf-8")
    assert "generalized_logistic_fixed_upper" in src
    assert "def _gen_logi_fixed_upper" not in src, (
        "the page re-implements the curve again; import it from "
        "TEXAS.models.logistics so it cannot diverge from the model")
