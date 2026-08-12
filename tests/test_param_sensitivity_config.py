"""
Guard against drift between the SI_code2a notebook and its headless runner.

``scripts/run_param_sensitivity.py`` and
``notebooks/manuscripts/SI_code2a_model_param_sensitivity_test.ipynb`` do the
same sampling and write the same files, so a reviewer can run either one. That
only holds while their configurations agree -- and they are separate files, so
nothing but this test makes them agree. Edit one, and this fails until you edit
the other.

The notebook is deliberately kept self-contained (it is the artefact reviewers
read top to bottom), which is what makes the duplication worth testing rather
than refactoring away.
"""
import ast
import json
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
NOTEBOOK = (REPO / "notebooks" / "manuscripts"
            / "SI_code2a_model_param_sensitivity_test.ipynb")
SCRIPT = REPO / "scripts" / "run_param_sensitivity.py"

pytestmark = pytest.mark.skipif(
    not (NOTEBOOK.exists() and SCRIPT.exists()),
    reason="SI_code2a notebook or its runner is not present",
)

# name -> whether order matters (lists compared as sets when it does not)
SHARED = {
    "CHAINS": True,
    "SEED": True,
    "WARMUPS": True,
    "MULTIPLIERS": True,
    "REF_WARMUP": True,
    "REF_SAMPLING": True,
    "DEFAULT_WARMUP": True,
    "DEFAULT_SAMPLING": True,
    "TEMPTYPE": True,
    "NO3_CUTOFF": True,
    "SD_PROXYOBS_MODE": True,
    "SD_PROXYOBS_BASE": True,
    "PRODUCTION_PROXY": True,
    "CORE_PARAMS": False,
    "GRID_MODELS": False,
    "PROXIES": False,
    "CRITERIA": False,
    # Part 3 (invT budget + M). Listed before the notebook grows a Part 3
    # section: names absent from the notebook are skipped, so this costs
    # nothing now and starts guarding the moment the section lands.
    "INVT_BUDGETS": False,
    "INVT_M_VALUES": False,
    "INVT_N_SITES": True,
    "INVT_N_BINS": True,
    "INVT_PRIOR_SIGMA_T": True,
    "INVT_CONSTRAINT": True,
    "INVT_CRITERIA": False,
}


def _eval(node):
    """literal_eval, extended to ``dict(a=1, b=2)`` which both files use."""
    if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            and node.func.id == "dict" and not node.args):
        return {kw.arg: _eval(kw.value) for kw in node.keywords}
    if isinstance(node, ast.Dict):
        return {_eval(k): _eval(v) for k, v in zip(node.keys, node.values)}
    if isinstance(node, (ast.List, ast.Tuple)):
        vals = [_eval(e) for e in node.elts]
        return vals if isinstance(node, ast.List) else tuple(vals)
    return ast.literal_eval(node)


def _literals(source: str) -> dict:
    """Top-level ``NAME = <literal>`` assignments, ignoring everything else."""
    out = {}
    for node in ast.parse(source).body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if not isinstance(target, ast.Name) or target.id not in SHARED:
                continue
            try:
                out[target.id] = _eval(node.value)
            except (ValueError, TypeError, AttributeError):
                pass  # computed, not a literal -- nothing to compare
    return out


# The notebook carries a plot colour per proxy; the runner never draws, so it
# does not. Compare only the keys that change what gets sampled.
PROXY_KEYS = ("column", "cren_rings")


def _notebook_config() -> dict:
    nb = json.loads(NOTEBOOK.read_text())
    merged = {}
    for cell in nb["cells"]:
        if cell["cell_type"] != "code":
            continue
        src = "".join(cell["source"])
        # Skip the QUICK override block: it deliberately reassigns the grid to
        # smoke-test values, and the runner expresses the same thing in _budgets().
        src = re.split(r"^if QUICK:", src, flags=re.M)[0]
        try:
            merged.update(_literals(src))
        except SyntaxError:
            continue
    return merged


@pytest.fixture(scope="module")
def configs():
    return _notebook_config(), _literals(SCRIPT.read_text())


@pytest.mark.parametrize("name", sorted(SHARED))
def test_shared_config_matches(configs, name):
    nb_cfg, sc_cfg = configs
    if name not in nb_cfg:
        pytest.skip(f"{name} is not a top-level literal in the notebook")
    assert name in sc_cfg, f"{name} is in the notebook but missing from {SCRIPT.name}"

    nb_val, sc_val = nb_cfg[name], sc_cfg[name]
    if name == "PROXIES":
        nb_val = {k: {j: v[j] for j in PROXY_KEYS} for k, v in nb_val.items()}
        sc_val = {k: {j: v[j] for j in PROXY_KEYS} for k, v in sc_val.items()}
    if not SHARED[name] and isinstance(nb_val, list):
        nb_val, sc_val = sorted(map(repr, nb_val)), sorted(map(repr, sc_val))
    assert nb_val == sc_val, (
        f"{name} differs between the notebook and {SCRIPT.name}:\n"
        f"  notebook: {nb_cfg[name]!r}\n"
        f"  script  : {sc_cfg[name]!r}\n"
        "Both run the same analysis and write the same files; update whichever "
        "is stale."
    )


def test_runner_covers_every_notebook_model(configs):
    """The runner must be able to produce every model the notebook plots."""
    nb_cfg, sc_cfg = configs
    if "GRID_MODELS" not in nb_cfg:
        pytest.skip("GRID_MODELS not readable from the notebook")
    nb_models = {m for _, m in nb_cfg["GRID_MODELS"]}
    sc_models = {m for _, m in sc_cfg["GRID_MODELS"]}
    missing = nb_models - sc_models
    assert not missing, f"notebook sweeps models the runner cannot produce: {missing}"


def test_core_params_cover_both_slope_conventions(configs):
    """
    The parent EIV model names its slopes beta_*, boundedT names them gamma_*.

    The accuracy check only measures parameters it finds by name, so dropping a
    convention would quietly exclude that model's two hardest-to-identify
    parameters from the very test meant to catch them -- and still report a pass.
    """
    nb_cfg, sc_cfg = configs
    for label, cfg in (("script", sc_cfg), ("notebook", nb_cfg)):
        if "CORE_PARAMS" not in cfg:
            continue
        params = set(cfg["CORE_PARAMS"])
        models = {m for _, m in cfg.get("GRID_MODELS", [])}
        if any("boundedT" in m for m in models):
            assert {"gamma_G23_crtp", "gamma_NO3_crtp"} <= params, (
                f"{label} sweeps a boundedT model but CORE_PARAMS has no gamma_* "
                "entries, so its slope parameters would be silently unchecked"
            )
        if any(m.endswith("_eiv") for m in models):
            assert {"beta_G23_crtp", "beta_NO3_crtp"} <= params, (
                f"{label} sweeps the additive EIV model but CORE_PARAMS has no "
                "beta_* entries"
            )


# --- Part 3 behaviour -------------------------------------------------------
# These exercise logic rather than configuration, but this is the only test
# module the runner has, and the logic below is what makes Part 3's answer
# generalise (or not) to the paleo sites the tuning is ultimately for.

@pytest.fixture(scope="module")
def runner():
    """Import the runner as a module. Its TEXAS imports are all function-local."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("_run_param_sensitivity", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    except Exception as exc:                      # pragma: no cover
        pytest.skip(f"runner not importable: {exc}")
    return mod


def _skewed_pool(n=1500, seed=0):
    """A proxy distribution shaped like the real one: dense middle, thin warm tail."""
    import numpy as np
    import pandas as pd
    rng = np.random.default_rng(seed)
    x = np.clip(rng.beta(2.5, 3.0, n), 0.01, 0.99) * 0.55 + 0.32
    return pd.DataFrame({"SST": 30 * (x - 0.32) / 0.55, "proxy": x})


def test_subset_covers_the_full_proxy_range(runner):
    """
    The warm, near-saturated end is where t_est is worst identified, and it is
    also where the paleo sites sit. A subset that stops short of the top of the
    range would tune the sampler on the easy part of the curve only.
    """
    import numpy as np
    pool = _skewed_pool()
    sub = runner.invt_subset(pool, "proxy", n=200)
    assert len(sub) == 200
    assert len(sub.drop_duplicates()) == 200, "sites were sampled twice"
    span = pool["proxy"].max() - pool["proxy"].min()
    assert sub["proxy"].max() >= pool["proxy"].max() - 0.05 * span
    assert sub["proxy"].min() <= pool["proxy"].min() + 0.05 * span


def test_subset_oversamples_the_saturated_tail_versus_random(runner):
    """
    The whole point of stratifying: a random draw would leave the flat end of
    the logistic barely represented, and the tuning would then not generalise
    to exactly the samples that stress it.
    """
    import numpy as np
    pool = _skewed_pool()
    sub = runner.invt_subset(pool, "proxy", n=200)
    edges = np.linspace(pool["proxy"].min(), pool["proxy"].max(), 11)
    top_pool = float((pool["proxy"] >= edges[-3]).mean())
    top_sub = float((sub["proxy"] >= edges[-3]).mean())
    assert top_sub > 1.5 * top_pool, (
        f"top of the proxy range is {top_sub:.1%} of the subset vs "
        f"{top_pool:.1%} of the pool -- barely better than random"
    )


def test_subset_is_deterministic(runner):
    """Same seed, same sites -- or two Part 3 cells are not comparable."""
    pool = _skewed_pool()
    a = runner.invt_subset(pool, "proxy", n=120)
    b = runner.invt_subset(pool, "proxy", n=120)
    assert a.equals(b)


def test_lock_is_not_released_by_a_forced_run(runner, tmp_path, monkeypatch):
    """
    --force-lock steals a live run's lockfile. Releasing it on the way out
    would leave that run unprotected against a third instance -- the very
    collision the lock exists to prevent.
    """
    import json
    import os
    lockfile = tmp_path / ".run.lock"
    monkeypatch.setattr(runner, "LOCKFILE", lockfile)
    monkeypatch.setattr(runner, "RESULTS_DIR", tmp_path)
    monkeypatch.setattr(runner, "_pid_alive", lambda pid: True)
    lockfile.write_text(json.dumps({"pid": os.getpid() + 1, "started": "x"}))

    with runner.single_instance(force=True):
        pass

    assert lockfile.exists(), "a forced run deleted the live run's lock"
    assert json.loads(lockfile.read_text())["pid"] != os.getpid()


def test_lock_is_released_by_its_owner(runner, tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "LOCKFILE", tmp_path / ".run.lock")
    monkeypatch.setattr(runner, "RESULTS_DIR", tmp_path)
    with runner.single_instance():
        assert (tmp_path / ".run.lock").exists()
    assert not (tmp_path / ".run.lock").exists()
