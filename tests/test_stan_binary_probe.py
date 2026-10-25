"""StanCompiler must not condemn a healthy compiled model.

get_model() probes an existing binary and, on a non-zero exit, deletes it and drops the
in-memory cache so the model is rebuilt. The probe therefore has to be an argument CmdStan
ACCEPTS. It used to be ``--version``, which a CmdStan executable rejects outright --

    $ ./latfit_logistic --version
    --version is either mistyped or misplaced.
    A method must be specified!            # exit 1

-- so every healthy binary was condemned and recompiled on EVERY get_model() call, while the
warning blamed Docker and reported a hardcoded "exit code 127". Measured in gdgt-db-workspace:
one precompute cell went from ~28 recompiles to 4, one per form.

It also made concurrent runs unsafe for a reason that looked like a Stan quirk: a second
process deleting the binary a first was sampling with. That is why callers there have to give
every parallel run its own build directory.
"""
from __future__ import annotations

import subprocess

import pytest

from TEXAS import StanCompiler


def _probe_arg_from_source() -> str:
    """The argument get_model actually probes with, read off the source."""
    import inspect
    import re
    src = inspect.getsource(StanCompiler.get_model)
    m = re.search(r"\[str\(binary_path\),\s*\"([^\"]+)\"\]", src)
    assert m, "get_model no longer probes the binary with a single literal argument"
    return m.group(1)


def test_the_probe_argument_is_one_cmdstan_accepts():
    """A regression guard that needs no compiler: ``--version`` and ``--help`` are rejected by
    every CmdStan executable, so neither can ever be the probe."""
    assert _probe_arg_from_source() not in ("--version", "--help", "-v", "-h")


@pytest.mark.skipif(not pytest.importorskip("cmdstanpy", reason="cmdstanpy not installed"),
                    reason="cmdstanpy not installed")
def test_a_healthy_binary_answers_the_probe(tmp_path):
    """Compile a trivial model and check the real probe exits 0 on it.

    If this fails, get_model will delete every binary it is given and recompile forever.
    """
    from cmdstanpy import CmdStanModel

    stan = tmp_path / "probe_ok.stan"
    stan.write_text("parameters { real x; } model { x ~ std_normal(); }\n", encoding="utf-8")
    model = CmdStanModel(stan_file=stan)
    binary = stan.with_suffix("")
    assert binary.exists(), "cmdstanpy did not leave an executable beside the source"

    arg = _probe_arg_from_source()
    r = subprocess.run([str(binary), arg], capture_output=True, timeout=60)
    assert r.returncode == 0, (
        f"the probe {arg!r} exits {r.returncode} on a freshly compiled, working binary, so "
        f"get_model would delete it and recompile on every call: "
        f"{(r.stdout + r.stderr).decode(errors='replace')[:200]}")


@pytest.mark.skipif(not pytest.importorskip("cmdstanpy", reason="cmdstanpy not installed"),
                    reason="cmdstanpy not installed")
def test_a_broken_binary_still_fails_the_probe(tmp_path):
    """The check this was written for must keep working: something that is not a runnable
    CmdStan executable has to come back non-zero so it is rebuilt."""
    fake = tmp_path / "not_a_model"
    fake.write_bytes(b"#!/bin/sh\nexit 127\n")
    fake.chmod(0o755)
    r = subprocess.run([str(fake), _probe_arg_from_source()], capture_output=True, timeout=30)
    assert r.returncode != 0
