"""The shipped Stan model set, and the archive that keeps the rest runnable.

`src/TEXAS/stan_models/` was pruned from 17 models to 9 on 2026-09-03; the other
8 moved to `archive/submission-2026-04/stan_models/`. Three things have to hold
after a move like that, and none of them fails loudly on its own:

1. Every model the selector can still choose has to exist. A missing one
   surfaces as a compile-time file error after the user has already waited for
   data assembly.
2. The archived models have to stay reachable by plain stem, because the SI
   notebooks and the refit scripts name the additive-EIV comparison arm that
   way. If the fallback breaks, `SI_code02a` fails only on a cold cache -- the
   one run nobody does before submitting.
3. The name grammar in `utils/naming.py` must keep decoding the archived
   variants, or every case id already written to disk and to Zenodo stops
   resolving.
"""
from pathlib import Path

import pytest

from TEXAS.stan.compiler import StanCompiler
from TEXAS.stan.invT import _select_invT_stan_file, _SHIPPED_CONSTRAINTS
from TEXAS.utils.naming import CONSTRAINT_DECODE
from TEXAS.utils.paths import STAN_MODELS_DIR, STAN_ARCHIVE_DIR

ARCHIVED = [
    "gen_logi_fixed_hier_crtp_multiv_priorApprox_eiv",
    "gen_logi_fixed_hier_crtp_multiv_priorApprox",
    "gen_logi_fixed_hier_crtp_multiv",
    "gen_logi_fixed_culmesocore",
    "invT_gen_logi_fixed_univ_unconstrained",
    "invT_gen_logi_fixed_multiv_unconstrained",
    "invT_gen_logi_fixed_univ_marginal_hard_constraint",
    "invT_gen_logi_fixed_multiv_marginal_hard_constraint",
]

# The T0-shift arm only ever had the multiv/unconstrained inverse model. These
# were never written, so they are not regressions from the archive move -- they
# are caught at runtime by the FileNotFoundError in `stan/invT.py`, which says
# so explicitly.
NEVER_EXISTED = {
    "invT_gen_logi_fixed_univ_marginal_unconstrained_t0shift.stan",
    "invT_gen_logi_fixed_univ_marginal_truncated_prior_t0shift.stan",
    "invT_gen_logi_fixed_multiv_marginal_truncated_prior_t0shift.stan",
}

needs_archive = pytest.mark.skipif(
    STAN_ARCHIVE_DIR is None,
    reason="archive/ is a source-checkout directory; absent in a wheel install",
)


def test_shipped_set_is_exactly_nine():
    """A model added to the shipped dir should be a deliberate act."""
    shipped = sorted(p.name for p in STAN_MODELS_DIR.glob("*.stan"))
    assert len(shipped) == 9, f"expected 9 shipped models, found {len(shipped)}: {shipped}"


@needs_archive
def test_archived_models_are_in_the_archive_not_the_package():
    for stem in ARCHIVED:
        assert not (STAN_MODELS_DIR / f"{stem}.stan").exists(), \
            f"{stem} was archived but is back in the shipped directory"
        assert (STAN_ARCHIVE_DIR / f"{stem}.stan").exists(), \
            f"{stem} is missing from the archive -- it was moved, not deleted"


def test_every_selectable_invT_model_exists():
    """The selector must not be able to name a file that does not ship."""
    missing = []
    for predictors in ({}, {"gdgt23ratio": True}):
        for constraint in sorted(_SHIPPED_CONSTRAINTS):
            for bounded in (False, True):
                name = _select_invT_stan_file(
                    {"M": 100}, predictors,
                    constraint_type=constraint, bounded=bounded)
                if not (STAN_MODELS_DIR / name).exists() and name not in NEVER_EXISTED:
                    missing.append(name)
    assert not missing, f"selector can choose models that do not ship: {missing}"


@pytest.mark.parametrize("constraint", ["hard_constraint", "reparameterized", "soft"])
def test_withdrawn_constraints_raise_with_a_useful_message(constraint):
    """Fail at the argument, not later at a missing file."""
    with pytest.raises(ValueError) as exc:
        _select_invT_stan_file({"M": 100}, {}, constraint_type=constraint)
    assert "truncated_prior" in str(exc.value), "the error should name the valid values"


def test_ensemble_model_type_raises():
    """`ensemble` built names archived in 2026-04; it had been broken since."""
    with pytest.raises(ValueError) as exc:
        _select_invT_stan_file({"M": 100}, {}, model_type="ensemble")
    assert "stan_model_path" in str(exc.value), "the error should name the escape hatch"


@needs_archive
def test_archived_models_still_resolve_by_plain_stem():
    """What keeps SI_code02a and the refit scripts working on a cold cache.

    They pass a bare stem, and that stem is also written to `stan_model_name`,
    so the fallback must resolve without the caller substituting a path.
    """
    compiler = StanCompiler()
    for stem in ARCHIVED:
        resolved = compiler.resolve_stan_path(stem)
        assert resolved.exists(), f"{stem} does not resolve"
        assert resolved.parent == STAN_ARCHIVE_DIR


def test_shipped_models_are_not_shadowed_by_the_archive():
    compiler = StanCompiler()
    for p in STAN_MODELS_DIR.glob("*.stan"):
        assert compiler.resolve_stan_path(p.stem).parent == STAN_MODELS_DIR


@needs_archive
def test_absolute_paths_pass_through_untouched():
    target = STAN_ARCHIVE_DIR / "gen_logi_fixed_culmesocore.stan"
    assert StanCompiler().resolve_stan_path(target) == target


def test_missing_model_reports_the_shipped_directory():
    """A genuine typo must not be reported as living in the archive."""
    resolved = StanCompiler().resolve_stan_path("no_such_model_anywhere")
    assert resolved.parent == STAN_MODELS_DIR
    assert not resolved.exists()


def test_name_grammar_still_decodes_withdrawn_constraints():
    """Reconstructions already on disk and on Zenodo carry these codes."""
    for code, name in [("u", "unconstrained"), ("h", "hard_constraint"),
                       ("t", "truncated_prior"), ("r", "reparameterized"),
                       ("s", "soft")]:
        assert CONSTRAINT_DECODE[code] == name, (
            f"case ids using '{code}' would stop resolving; CONSTRAINT_CODES is a "
            "name grammar, not a list of selectable options")
