"""Guards for the ASCII sanitization of Stan build copies.

cmdstanpy reads each .stan file with ``open(path, 'r')`` and no explicit
encoding, so it decodes with the platform locale codec — cp1252 on a default
Windows install. Any non-ASCII byte (box-drawing banners, Greek symbols,
subscripts, ... commonly used in model comments) then raises
``UnicodeDecodeError`` at import/compile time.

``StanCompiler`` defends against this by copying an ASCII-sanitized version of
each model into the build dir (see ``TEXAS.stan.compiler._copy_stan_ascii``).
Source files may keep their Unicode; only the disposable build copy is
transliterated. These tests assert that invariant holds for *every* real model,
so a newly added model with fancy comments can never reintroduce the crash.
"""
import pytest

from TEXAS.stan.compiler import _copy_stan_ascii, _stan_text_to_ascii
from TEXAS.utils.paths import STAN_MODELS_DIR

STAN_FILES = sorted(STAN_MODELS_DIR.glob("*.stan"))


def test_stan_models_dir_has_models():
    # Guard against the parametrized tests silently passing on an empty glob.
    assert STAN_FILES, f"no .stan files found under {STAN_MODELS_DIR}"


@pytest.mark.parametrize("stan_file", STAN_FILES, ids=lambda p: p.name)
def test_sanitized_source_is_cp1252_readable(stan_file):
    """After sanitization, every model must read back under cmdstanpy's codec."""
    text = stan_file.read_bytes().decode("utf-8")
    ascii_text = _stan_text_to_ascii(text)

    # Pure ASCII ...
    assert ascii_text.isascii(), f"{stan_file.name}: non-ASCII survived sanitization"
    # ... and therefore decodable by cp1252 (what cmdstanpy uses on Windows).
    ascii_text.encode("cp1252").decode("cp1252")


@pytest.mark.parametrize("stan_file", STAN_FILES, ids=lambda p: p.name)
def test_copy_stan_ascii_writes_locale_readable_file(stan_file, tmp_path):
    """End-to-end: the build copy must open cleanly the way cmdstanpy opens it."""
    dest = tmp_path / stan_file.name
    _copy_stan_ascii(stan_file, dest)

    # Mimic cmdstanpy/model.py: open(path, 'r') with the Windows locale codec.
    with open(dest, "r", encoding="cp1252") as fd:
        program = fd.read()
    assert program.isascii()


def test_ascii_source_passes_through_unchanged():
    """ASCII-only content must be byte-identical, so clean models are untouched."""
    plain = "data { int<lower=0> N; }\nmodel { }\n"
    assert _stan_text_to_ascii(plain) == plain


def test_known_symbols_transliterate_readably():
    """Common comment symbols become readable ASCII rather than '?' placeholders."""
    sample = (
        "// ══ γ_G23 T₀ NO₃ log₁₀ "
        "−0.41 ≈ 22.5°C ⇒ β ∈ [b,1]"
    )
    out = _stan_text_to_ascii(sample)
    assert out.isascii()
    for expected in ("==", "gamma_G23", "T0", "NO3", "log10", "-0.41",
                     "~=", "22.5degC", "=>", "beta", "in"):
        assert expected in out, f"missing {expected!r} in {out!r}"
    # A readable transliteration should not fall back to placeholder '?'.
    assert "?" not in out
