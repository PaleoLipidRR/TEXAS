"""Tests for the opt-in CmdStan installer (TEXAS.install_cmdstan).

cmdstanpy.install_cmdstan is mocked throughout — these never download or compile
anything. They assert the TEXAS-specific behaviour layered on top: no-op when a
working install already resolves, and auto-overwrite when the target directory
exists but is a broken/partial install.
"""
import sys
from pathlib import Path

import TEXAS
from TEXAS.constants import RECOMMENDED_CMDSTAN_VERSION
from TEXAS.utils import install as install_mod


def test_install_cmdstan_is_exported():
    assert hasattr(TEXAS, "install_cmdstan")
    assert "install_cmdstan" in TEXAS.__all__


def test_noop_when_already_available(monkeypatch):
    """If find_cmdstan resolves, don't call cmdstanpy.install_cmdstan at all."""
    fake = Path("/opt/cmdstan/cmdstan-2.36.0")
    monkeypatch.setattr(install_mod, "find_cmdstan", lambda: fake)

    called = {"n": 0}
    fake_cmdstanpy = type(sys)("cmdstanpy")
    fake_cmdstanpy.install_cmdstan = lambda **kw: called.__setitem__("n", called["n"] + 1)
    monkeypatch.setitem(sys.modules, "cmdstanpy", fake_cmdstanpy)

    result = TEXAS.install_cmdstan(verbose=False)
    assert result == fake
    assert called["n"] == 0  # never attempted a real install


def test_auto_overwrite_on_broken_dir(monkeypatch, tmp_path):
    """A broken target dir forces overwrite=True even if caller passed False."""
    # find_cmdstan: first call raises (not found), second returns the fixed path
    resolved = tmp_path / "cmdstan-x"
    calls = {"n": 0}

    def fake_find():
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("not found")
        return resolved

    monkeypatch.setattr(install_mod, "find_cmdstan", fake_find)
    monkeypatch.setattr(install_mod, "_existing_target_is_broken", lambda v: True)

    seen = {}
    fake_cmdstanpy = type(sys)("cmdstanpy")
    fake_cmdstanpy.install_cmdstan = lambda **kw: seen.update(kw)
    monkeypatch.setitem(sys.modules, "cmdstanpy", fake_cmdstanpy)

    result = TEXAS.install_cmdstan(overwrite=False, verbose=False)
    assert seen["overwrite"] is True
    assert seen["version"] == RECOMMENDED_CMDSTAN_VERSION
    assert result == resolved


def test_returns_none_when_still_unresolved(monkeypatch):
    """If CmdStan still doesn't resolve after install, return None (not raise)."""
    monkeypatch.setattr(
        install_mod, "find_cmdstan", lambda: (_ for _ in ()).throw(RuntimeError())
    )
    monkeypatch.setattr(install_mod, "_existing_target_is_broken", lambda v: False)

    fake_cmdstanpy = type(sys)("cmdstanpy")
    fake_cmdstanpy.install_cmdstan = lambda **kw: None
    monkeypatch.setitem(sys.modules, "cmdstanpy", fake_cmdstanpy)

    result = TEXAS.install_cmdstan(verbose=False)
    assert result is None
