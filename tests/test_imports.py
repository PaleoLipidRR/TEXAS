"""Smoke tests: TEXAS imports cleanly and top-level exports are callable."""



def test_import_texas():
    """import TEXAS succeeds without error."""
    import TEXAS  # noqa: F401


def test_version_is_string():
    """TEXAS.__version__ is a non-empty string."""
    import TEXAS
    assert isinstance(TEXAS.__version__, str)
    assert len(TEXAS.__version__) > 0


def test_predict_proxy_from_t_is_callable():
    """predict_proxy_from_T is exported and callable."""
    import TEXAS
    assert callable(TEXAS.predict_proxy_from_T)


def test_predict_t_from_proxyobs_is_callable():
    """predict_T_from_proxyObs is exported and callable."""
    import TEXAS
    assert callable(TEXAS.predict_T_from_proxyObs)


def test_load_posterior_is_callable():
    """load_posterior is exported and callable."""
    import TEXAS
    assert callable(TEXAS.load_posterior)


def test_generate_ensemble_auto_is_callable():
    """generate_ensemble_auto is exported and callable."""
    import TEXAS
    assert callable(TEXAS.generate_ensemble_auto)


def test_summarize_sampler_diagnostics_is_callable():
    """summarize_sampler_diagnostics is exported and callable."""
    import TEXAS
    assert callable(TEXAS.summarize_sampler_diagnostics)


def test_all_exports_importable():
    """Every name listed in __all__ can be imported from TEXAS."""
    import TEXAS
    for name in TEXAS.__all__:
        assert hasattr(TEXAS, name), f"TEXAS.__all__ lists '{name}' but it is not importable"


import pytest

# §9.6 deletions (2026-09-07). These six had no caller anywhere in src/, tests/,
# scripts/, streamlit_app/, notebooks/ or docs/ -- only their own re-export
# lines. Re-exporting one again would put an unused name back on the public
# surface, which is what the audit was for.
DELETED_TOP_LEVEL = ["generalized_logistic", "compute_density_based_range"]
DELETED_SUBMODULE = [
    ("TEXAS.utils.naming", "default_version"),
    ("TEXAS.utils.naming", "describe_compset"),
    ("TEXAS.utils.paths", "get_repo_root"),
    ("TEXAS.utils.system_info", "save_system_summary"),
    ("TEXAS.models.logistics", "generalized_logistic"),
    ("TEXAS.plotting.range_utils", "compute_density_based_range"),
    ("TEXAS.stan", "get_repo_root"),
    ("TEXAS.utils", "get_repo_root"),
    ("TEXAS.utils", "save_system_summary"),
]


@pytest.mark.parametrize("name", DELETED_TOP_LEVEL)
def test_deleted_names_are_not_top_level_exports(name):
    """A deleted helper must not come back through TEXAS/__init__.py."""
    import TEXAS
    assert name not in TEXAS.__all__
    assert not hasattr(TEXAS, name)


@pytest.mark.parametrize("module,name", DELETED_SUBMODULE)
def test_deleted_names_are_gone_from_their_module(module, name):
    """Neither the definition nor any re-export of it survives."""
    import importlib
    mod = importlib.import_module(module)
    assert not hasattr(mod, name), f"{module}.{name} is still exported"
    assert name not in getattr(mod, "__all__", []), f"{module}.__all__ lists {name}"


def test_surviving_neighbours_still_export():
    """The deletions were surgical: their file-mates are untouched."""
    import TEXAS
    for kept in ("logistic", "logistic_fixed_upper", "inverse_logistic_fixed_upper",
                 "generalized_logistic_fixed_upper", "compute_sample_range",
                 "compute_suffix_specific_range", "compute_dataset_specific_range"):
        assert kept in TEXAS.__all__ and hasattr(TEXAS, kept)
