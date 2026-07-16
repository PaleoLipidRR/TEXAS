"""Tests for the Windows C++ toolchain shim (``ensure_cxx_toolchain``).

The shim prepends the RTools ``g++`` to PATH before Stan compiles so CmdStan's
prebuilt objects are not linked against an incompatible libstdc++ (the classic
Strawberry-Perl ``undefined reference to std::istream::seekg`` failure).

These assert on contract and safety, not on whether RTools is installed, so they
pass on every platform in CI.
"""
import os
import sys

import pytest

from TEXAS.utils.paths import ensure_cxx_toolchain


def test_returns_tuple_of_str():
    result = ensure_cxx_toolchain()
    assert isinstance(result, tuple)
    assert all(isinstance(p, str) for p in result)


@pytest.mark.skipif(os.name == "nt", reason="no-op behaviour is for non-Windows")
def test_noop_off_windows():
    """Off Windows the shim must do nothing and touch nothing."""
    before = os.environ.get("PATH", "")
    assert ensure_cxx_toolchain() == ()
    assert os.environ.get("PATH", "") == before


def test_never_raises_even_with_bogus_install_dir():
    """A missing RTools root must degrade to a no-op, not raise."""
    # An install_dir with no RTools* under it → cmdstanpy raises ValueError
    # internally; the shim must swallow it and return ().
    result = ensure_cxx_toolchain(install_dir=os.path.join(os.sep, "no", "such", "rtools"))
    assert isinstance(result, tuple)


def test_preserves_existing_path_entries():
    """Whatever the shim does, it must not drop entries already on PATH."""
    before = set(os.environ.get("PATH", "").split(os.pathsep))
    ensure_cxx_toolchain()
    after = set(os.environ.get("PATH", "").split(os.pathsep))
    assert before <= after, "ensure_cxx_toolchain dropped existing PATH entries"


@pytest.mark.skipif(sys.platform != "win32", reason="RTools prepend is Windows-only")
def test_idempotent_on_windows():
    """Repeated calls must not keep growing PATH (cmdstanpy de-dupes)."""
    ensure_cxx_toolchain()
    path_once = os.environ.get("PATH", "")
    ensure_cxx_toolchain()
    path_twice = os.environ.get("PATH", "")
    assert path_once == path_twice
