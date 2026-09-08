"""The shipped Stan model set, and the archive that keeps the rest runnable.

`src/TEXAS/stan_models/` was pruned from 17 models to 9 on 2026-09-03 and to 7
on 2026-09-07. Eight went to `archive/submission-2026-04/stan_models/`, which
`STAN_ARCHIVE_DIR` covers; the two truncated-prior inverses went to
`archive/pre-submission/stan_models/`, which it deliberately does not -- nothing
can select them by stem now that `constraint_type` is gone, so an absolute path
is the only route and the only one needed. Three things have to hold after a
move like that, and none of them fails loudly on its own:

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

import pytest

from TEXAS.stan.compiler import StanCompiler
from TEXAS.stan.invT import _select_invT_stan_file, _SHIPPED_CONSTRAINTS
from TEXAS.utils.naming import CONSTRAINT_DECODE
from TEXAS.utils.paths import STAN_MODELS_DIR, STAN_ARCHIVE_DIR, PROJECT_ROOT

# The two truncated-prior inverses archived 2026-09-07. Unlike everything else
# in ARCHIVED, these live in `archive/pre-submission/stan_models/`, which
# `STAN_ARCHIVE_DIR` deliberately does not cover -- once `constraint_type` left
# the public API nothing can construct their names by stem, so they resolve by
# absolute path only. Tests that assert the plain-stem fallback (property 2 in
# the module docstring) must not apply it to these two.
PRE_SUBMISSION_TRUNCATED_PRIOR = {
    "invT_gen_logi_fixed_univ_marginal_truncated_prior",
    "invT_gen_logi_fixed_multiv_marginal_truncated_prior",
}
PRE_SUBMISSION_STAN_DIR = PROJECT_ROOT / "archive" / "pre-submission" / "stan_models"

ARCHIVED = [
    "gen_logi_fixed_hier_crtp_multiv_priorApprox_eiv",
    "gen_logi_fixed_hier_crtp_multiv_priorApprox",
    "gen_logi_fixed_hier_crtp_multiv",
    "gen_logi_fixed_culmesocore",
    "invT_gen_logi_fixed_univ_unconstrained",
    "invT_gen_logi_fixed_multiv_unconstrained",
    "invT_gen_logi_fixed_univ_marginal_hard_constraint",
    "invT_gen_logi_fixed_multiv_marginal_hard_constraint",
    # Archived 2026-09-07: docs/why_plugin_p50_differs.md, the only page that
    # explained them, is removed in the same pass, and the manuscript's
    # reconstructions are all unconstrained.
    "invT_gen_logi_fixed_univ_marginal_truncated_prior",
    "invT_gen_logi_fixed_multiv_marginal_truncated_prior",
]

# The T0-shift arm only ever had the multiv/unconstrained inverse model. This
# was never written, so it is not a regression from an archive move -- it is
# caught at runtime by the FileNotFoundError in `stan/invT.py`, which says so.
# The two truncated_prior t0shift names that used to sit here are unreachable
# now that `truncated_prior` is not a shipped constraint.
NEVER_EXISTED = {
    "invT_gen_logi_fixed_univ_marginal_unconstrained_t0shift.stan",
}

needs_archive = pytest.mark.skipif(
    STAN_ARCHIVE_DIR is None,
    reason="archive/ is a source-checkout directory; absent in a wheel install",
)


def test_shipped_set_is_exactly_seven():
    """A model added to the shipped dir should be a deliberate act."""
    shipped = sorted(p.name for p in STAN_MODELS_DIR.glob("*.stan"))
    assert len(shipped) == 7, f"expected 7 shipped models, found {len(shipped)}: {shipped}"


@needs_archive
def test_archived_models_are_in_the_archive_not_the_package():
    for stem in ARCHIVED:
        assert not (STAN_MODELS_DIR / f"{stem}.stan").exists(), \
            f"{stem} was archived but is back in the shipped directory"
        archive_dir = (PRE_SUBMISSION_STAN_DIR if stem in PRE_SUBMISSION_TRUNCATED_PRIOR
                       else STAN_ARCHIVE_DIR)
        assert (archive_dir / f"{stem}.stan").exists(), \
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


@pytest.mark.parametrize("constraint",
                         ["truncated_prior", "hard_constraint", "reparameterized", "soft"])
def test_withdrawn_constraints_raise_with_a_useful_message(constraint):
    """Fail at the argument, not later at a missing file."""
    with pytest.raises(ValueError) as exc:
        _select_invT_stan_file({"M": 100}, {}, constraint_type=constraint)
    assert "unconstrained" in str(exc.value), "the error should name the valid value"
    assert "archive/pre-submission" in str(exc.value), \
        "the error should say where the truncated-prior models went"


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
        if stem in PRE_SUBMISSION_TRUNCATED_PRIOR:
            continue  # deliberately absolute-path-only; see module docstring
        resolved = compiler.resolve_stan_path(stem)
        assert resolved.exists(), f"{stem} does not resolve"
        assert resolved.parent == STAN_ARCHIVE_DIR


def test_truncated_prior_models_do_not_resolve_by_plain_stem():
    """They were archived deliberately unreachable by stem -- see module docstring."""
    compiler = StanCompiler()
    for stem in PRE_SUBMISSION_TRUNCATED_PRIOR:
        target = PRE_SUBMISSION_STAN_DIR / f"{stem}.stan"
        assert target.exists(), f"{stem} is missing from {PRE_SUBMISSION_STAN_DIR}"
        resolved = compiler.resolve_stan_path(stem)
        assert resolved != target, f"{stem} resolves by stem -- it should not"


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


def test_constraint_type_and_min_temp_are_not_public_parameters():
    """They left the API with the models they selected (2026-09-07)."""
    import inspect

    from TEXAS.predict import predict_T_from_proxyObs
    from TEXAS.stan.invT import get_invT_posterior

    for fn in (predict_T_from_proxyObs, get_invT_posterior):
        params = inspect.signature(fn).parameters
        assert "constraint_type" not in params, f"{fn.__name__} still takes constraint_type"
        assert "min_temp" not in params, f"{fn.__name__} still takes min_temp"


def test_name_grammar_still_decodes_withdrawn_constraints():
    """Reconstructions already on disk and on Zenodo carry these codes."""
    for code, name in [("u", "unconstrained"), ("h", "hard_constraint"),
                       ("t", "truncated_prior"), ("r", "reparameterized"),
                       ("s", "soft")]:
        assert CONSTRAINT_DECODE[code] == name, (
            f"case ids using '{code}' would stop resolving; CONSTRAINT_CODES is a "
            "name grammar, not a list of selectable options")
