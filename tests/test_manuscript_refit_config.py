"""
Guard the refit runner against drifting from SI03.

``scripts/run_manuscript_refits.py`` rebuilds SI03's paleo inputs -- site lists,
depth windows, PETM priors, NO3 scenarios -- because the notebook builds them
inline and there is nothing importable. Duplication is the price; this test is
what stops it becoming divergence.

It matters more here than for the sensitivity runner. A refit whose inputs
differ from the notebook's produces posteriors that look right, load fine, and
quietly answer a different question than the figures claim.
"""
import ast
import json
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
NOTEBOOK = REPO / "notebooks" / "manuscripts" / "SI_code03_paleo_showcases.ipynb"
SCRIPT = REPO / "scripts" / "run_manuscript_refits.py"

pytestmark = pytest.mark.skipif(
    not (NOTEBOOK.exists() and SCRIPT.exists()),
    reason="SI03 or the refit runner is not present",
)


def _nb_source() -> str:
    nb = json.loads(NOTEBOOK.read_text())
    return "\n".join("".join(c["source"]) for c in nb["cells"]
                     if c["cell_type"] == "code")


@pytest.fixture(scope="module")
def runner():
    import importlib.util
    spec = importlib.util.spec_from_file_location("_run_manuscript_refits", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    except Exception as exc:                                # pragma: no cover
        pytest.skip(f"runner not importable: {exc}")
    return mod


@pytest.fixture(scope="module")
def nb():
    return _nb_source()


def test_petm_depth_windows_match(runner, nb):
    """The PETM body is defined by these windows; a shifted edge re-labels samples."""
    for site, (lo, hi) in {**runner.PETM_WINDOW_SAMPLEDEPTH,
                           **runner.PETM_WINDOW_MBSF}.items():
        assert re.search(rf"['\"]{re.escape(site)}['\"]\s*:\s*\(\s*{lo}\s*,\s*{hi}\s*\)", nb), (
            f"{site} window ({lo}, {hi}) is not the one SI03 uses")


def test_petm_priors_match(runner, nb):
    """A wrong prior mean moves every reconstruction at that site."""
    for site, (inside, outside) in runner.PETM_PRIORS.items():
        for value in (inside, outside):
            assert re.search(rf"prior_mu_T'\]\s*=\s*{value}\b", nb), (
                f"prior {value} degC for {site} does not appear in SI03")


def test_site_lists_match(runner, nb):
    for site in runner.GIG_SITES:
        assert site in nb, f"{site} is not a GIG site in SI03"
    assert "'ODP959'" in nb and "South Dover Bridge" in nb


def test_scenario_tags_match(runner, nb):
    """Run and load must agree on the tag, or a reconstruction is written where
    nothing looks for it."""
    for sc in runner.GIG_SCENARIOS + runner.PETM_SCENARIOS:
        assert f"'{sc['tag']}'" in nb, (
            f"scenario tag {sc['tag']!r} is not in SI03's registry")


def test_no_date_tags_anywhere(runner, nb):
    """Filenames carry no dates; the run date lives in run_timestamp."""
    for sc in runner.GIG_SCENARIOS + runner.PETM_SCENARIOS:
        assert not re.fullmatch(r"\d{6}", sc["tag"]), sc
        assert not re.search(r"\d{6}", sc["tag"]), sc
    src = SCRIPT.read_text()
    for node in ast.parse(src).body:
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant):
            if isinstance(node.value.value, str):
                assert not re.fullmatch(r"\d{6}", node.value.value), ast.dump(node)


def test_both_arms_share_one_forward_budget(runner):
    """
    The comparison is only worth something if the model is the only difference.
    A per-model budget would sample the two arms differently.
    """
    assert isinstance(runner.FWD_WARMUP, int) and isinstance(runner.FWD_SAMPLING, int)
    assert len(runner.VARIANTS) == 2
    # one budget, applied by a single helper both arms go through
    kw = runner._fwd_kwargs()
    assert kw["iter_warmup"] == runner.FWD_WARMUP
    assert kw["iter_sampling"] == runner.FWD_SAMPLING
    assert kw["seed"] == runner.SEED and kw["chains"] == runner.CHAINS


def test_proxy_and_cutoff_match_si03(runner, nb):
    assert f"'{runner.PROXY}'" in nb
    assert re.search(rf"no3_thershold_dict\s*=\s*{{'thermoT':\s*'{runner.NO3_CUTOFF}'",
                     nb) or f"{runner.NO3_CUTOFF}" in nb


def test_audit_reports_not_ready_on_an_empty_manifest(runner, tmp_path, monkeypatch):
    """The audit must not pass by default -- an empty run is not a ready run."""
    monkeypatch.setattr(runner, "RESULTS_DIR", tmp_path)
    monkeypatch.setattr(runner, "MANIFEST", tmp_path / "manifest.csv")
    monkeypatch.setattr(runner, "AUDIT_JSON", tmp_path / "audit.json")
    report = runner.audit()
    assert report["ok"] is False


def test_inverse_call_binds_against_the_real_signature(runner):
    """
    The refit's inverse stage failed on its first reconstruction with an
    unexpected-keyword TypeError, an hour into a run, after the whole forward
    stage had completed. stan.invT's low-level function takes
    fwd_posterior_name; TEXAS.predict's wrapper takes fwd_posterior for both a
    name and a Dataset. Binding the call is free and catches that at import
    time rather than after the expensive part.
    """
    import inspect
    import numpy as np
    pytest.importorskip("TEXAS.predict")
    from TEXAS.data.builder import InvTConfig
    from TEXAS.predict import predict_T_from_proxyObs

    call = dict(
        proxyObs=[0.5, 0.6], prior_mu_t=20.0, prior_sigma_t=runner.PRIOR_SIGMA_T,
        fwd_posterior="tx.v026.GHPU.sst.sri03.p0.001",
        predictors={"gdgt23ratio": np.array([1.0, 1.1]), "no3": 0.1},
        site_name="X", temptype="SST", proxy_name=runner.PROXY,
        config=InvTConfig(n_draws=runner.INV_M),
        chains=runner.CHAINS, iter_warmup=runner.INV_WARMUP,
        iter_sampling=runner.INV_SAMPLING, seed=runner.SEED,
        save_results=True, filename_tag="no3_01",
    )
    inspect.signature(predict_T_from_proxyObs).bind(**call)
