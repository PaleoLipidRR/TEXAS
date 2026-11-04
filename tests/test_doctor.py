"""Tests for the environment diagnostic (TEXAS.doctor) and the CmdStan version
single-source-of-truth constant.

These inspect the *real* environment (no mocks). They assert on structure and
types, not on whether CmdStan happens to be installed, so they pass in CI
regardless of whether a CmdStan toolchain is present.
"""
import re

import TEXAS
from TEXAS.constants import RECOMMENDED_CMDSTAN_VERSION


def test_version_from_makefile_reads_conda_forge_layout(tmp_path):
    # conda-forge installs CmdStan at $CONDA_PREFIX/bin/cmdstan with no version
    # in the path; the makefile is then the only place the version is written.
    from TEXAS.utils.doctor import _version_from_makefile
    (tmp_path / "makefile").write_text(
        "# CmdStan makefile\nCMDSTAN_VERSION := 2.36.0\nO ?= 1\n", encoding="utf-8"
    )
    assert _version_from_makefile(tmp_path) == "2.36.0"
    assert _version_from_makefile(tmp_path / "missing") is None


def test_recommended_cmdstan_version_is_semver():
    assert isinstance(RECOMMENDED_CMDSTAN_VERSION, str)
    assert re.fullmatch(r"\d+\.\d+\.\d+", RECOMMENDED_CMDSTAN_VERSION)


def test_doctor_is_exported_from_package():
    assert hasattr(TEXAS, "doctor")
    assert "doctor" in TEXAS.__all__


def test_doctor_returns_expected_structure():
    report = TEXAS.doctor(verbose=False)
    assert isinstance(report, dict)
    for key in (
        "texas_version",
        "python_version",
        "cmdstanpy",
        "cmdstan",
        "compiler",
        "cache_dir",
        "sampling_ready",
    ):
        assert key in report, f"missing key: {key}"
    assert isinstance(report["sampling_ready"], bool)
    assert isinstance(report["cmdstanpy"]["installed"], bool)
    # the report echoes the single-source-of-truth version
    assert report["cmdstan"]["recommended"] == RECOMMENDED_CMDSTAN_VERSION


def test_sampling_ready_requires_cmdstan_and_compiler():
    report = TEXAS.doctor(verbose=False)
    expected = report["cmdstan"]["found"] and report["compiler"]["found"]
    assert report["sampling_ready"] == expected


def test_cli_main_returns_exit_code():
    from TEXAS.utils.doctor import _cli_main

    code = _cli_main([])
    assert code in (0, 1)
