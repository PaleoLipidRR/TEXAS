"""A compiled model must survive a new session instead of being recompiled.

``StanCompiler.get_model()`` probes an existing binary before reusing it, to
catch one built for another environment (Docker vs. host, another OS). The
probe used to run ``model --version``, which CmdStan model executables reject
with exit status 1, so every healthy binary was deleted and recompiled at the
start of every new Python process. These tests compile a tiny model, then ask a
fresh ``StanCompiler`` (empty in-memory cache, as in a new session) for it again.
"""

import os
import stat
import sys
import warnings

import pytest

from TEXAS.utils.paths import find_cmdstan

try:
    find_cmdstan()
    _HAVE_CMDSTAN = True
except RuntimeError:
    _HAVE_CMDSTAN = False

pytestmark = pytest.mark.skipif(not _HAVE_CMDSTAN, reason="CmdStan not installed")

TINY_MODEL = "parameters { real mu; } model { mu ~ normal(0, 1); }\n"


@pytest.fixture
def compiled(tmp_path):
    """Compile TINY_MODEL into a private build dir; return (stan_file, binary)."""
    from TEXAS.stan.compiler import StanCompiler

    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "tiny.stan").write_text(TINY_MODEL)
    build_dir = tmp_path / "build"
    build_dir.mkdir()

    compiler = StanCompiler(model_dir=src_dir)
    compiler.build_dir = build_dir
    compiler.get_model("tiny")

    binary = build_dir / ("tiny.exe" if sys.platform == "win32" else "tiny")
    assert binary.exists()
    return src_dir, build_dir, binary


def _fresh_compiler(src_dir, build_dir):
    from TEXAS.stan.compiler import StanCompiler

    compiler = StanCompiler(model_dir=src_dir)
    compiler.build_dir = build_dir
    return compiler


def test_healthy_binary_is_reused_across_sessions(compiled):
    src_dir, build_dir, binary = compiled
    mtime = binary.stat().st_mtime_ns

    with warnings.catch_warnings():
        warnings.simplefilter("error", RuntimeWarning)
        model = _fresh_compiler(src_dir, build_dir).get_model("tiny")

    assert binary.stat().st_mtime_ns == mtime, "binary was recompiled"
    assert model.exe_file is not None


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX shell script stand-in")
def test_binary_that_cannot_run_is_recompiled(compiled):
    """A binary that fails before argument parsing is replaced, and the warning
    reports its real exit code rather than a hard-coded one."""
    src_dir, build_dir, binary = compiled
    # Stand-in for a binary built elsewhere: exits 126 with a loader-style error.
    binary.write_text("#!/bin/sh\necho 'cannot execute binary file' >&2\nexit 126\n")
    binary.chmod(binary.stat().st_mode | stat.S_IXUSR)
    # Keep it newer than the .stan copy so cmdstanpy would otherwise reuse it.
    os.utime(binary, None)

    with pytest.warns(RuntimeWarning, match=r"exit code 126.*cannot execute"):
        _fresh_compiler(src_dir, build_dir).get_model("tiny")

    assert "cannot execute" not in binary.read_bytes().decode("latin-1")
