"""The browser walkthrough must not drift from the package it explains."""
from __future__ import annotations

import importlib.util
import inspect
import json
from pathlib import Path

import numpy as np
import pytest

import TEXAS
from TEXAS.quality import DEFAULT_PRIOR_DOMINATED_RATIO

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "docs" / "_scripts" / "build_gdgt_to_temperature.py"
SNAPSHOT = ROOT / "docs" / "_static" / "gdgt-to-temperature.data.json"
PAGE = ROOT / "docs" / "_static" / "gdgt-to-temperature.html"


@pytest.fixture(scope="module")
def snap():
    return json.loads(SNAPSHOT.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def builder():
    spec = importlib.util.spec_from_file_location("build_gdgt_to_temperature", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _posterior(ex, ens, T):
    """The Stan model's density for one sample, evaluated directly."""
    logn = np.log10(ex["no3"] + 1e-9) if 0 < ex["no3"] < 1.0 else 0.0
    t0e = ens["t0"] + ens["gG"] * ex["g23"] + ens["gN"] * logn
    mu = ens["b"][:, None] + (1 - ens["b"][:, None]) / (
        1 + np.exp(-ens["k"][:, None] * (T[None, :] - t0e[:, None]))
    ) ** (1 / ens["v"][:, None])
    z = (ex["ri"] - mu) / ens["sig"][:, None]
    like = (np.exp(-0.5 * z**2) / ens["sig"][:, None]).mean(0)
    return like * np.exp(-0.5 * ((T - ex["prior_mu"]) / ex["prior_sigma"]) ** 2)


def test_committed_page_matches_a_fresh_build(snap, builder):
    """Draws, Stan source, defaults and template: any drift changes the bytes."""
    fresh = builder.assemble(snap["runs"])
    assert fresh == snap
    assert builder.render(fresh) == PAGE.read_text(encoding="utf-8")


def test_sampler_settings_are_the_package_defaults(snap):
    sig = inspect.signature(TEXAS.predict_T_from_proxyObs).parameters
    assert snap["stan"]["warmup"] == sig["iter_warmup"].default
    assert snap["stan"]["sampling"] == sig["iter_sampling"].default
    assert snap["stan"]["chains"] == sig["chains"].default
    assert snap["meta"]["prior_dominated_ratio"] == DEFAULT_PRIOR_DOMINATED_RATIO


def test_stored_runs_match_the_density_the_page_computes(snap):
    """If the model changed, the stored Stan runs and the page's algebra part ways."""
    ens = {k: np.asarray(v) for k, v in snap["ens"].items()}
    T = np.linspace(*snap["meta"]["T"][:2], snap["meta"]["T"][2])
    for ex in snap["examples"]:
        post = _posterior(ex, ens, T)
        cdf = np.cumsum(post) / post.sum()
        direct = np.interp([0.16, 0.5, 0.84], cdf, T)
        stan = np.asarray(ex["stan"])[[1, 2, 3]]
        assert np.abs(direct - stan).max() < 0.5, ex["record"]


def test_page_flag_rules_reproduce_the_stored_flags(snap):
    """The page applies quality.py's rules; the claim that they agree must hold."""
    b = np.asarray(snap["ens"]["b"])
    R = snap["meta"]["ranges"]
    for ex in snap["examples"]:
        got = snap["runs"][ex["record"]]["flags"]
        assert got["proxy_below_floor"] == bool((ex["ri"] < b).mean() > 0.5)
        assert got["proxy_above_ceiling"] == (ex["ri"] > 1)
        assert got["proxy_extrapolated"] == (not R["proxy"][0] <= ex["ri"] <= R["proxy"][1])
        assert got["predictor_extrapolated"] == (
            not R["g23"][0] <= ex["g23"] <= R["g23"][1]
            or not R["no3"][0] <= ex["no3"] <= R["no3"][1]
        )
        assert got["no3_correction_inactive"] == (not 0 < ex["no3"] < snap["meta"]["cutoff"])


@pytest.mark.parametrize(
    "token",
    ["gdgtws", "gridT", "censor", "midpoint", "repeat injections", "gdgt-db", "fonts.googleapis",
     "centred", "normalis", "__DATA__"],
)
def test_page_carries_nothing_from_the_private_workspace(token):
    template = (ROOT / "docs" / "_scripts" / "gdgt_to_temperature_template.html").read_text(encoding="utf-8")
    assert token.lower() not in template.replace("__DATA__", "", 1).lower()
