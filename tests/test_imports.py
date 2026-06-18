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
