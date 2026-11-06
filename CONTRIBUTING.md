# Contributing to TEXAS

Thank you for your interest in contributing to `texas-psm`.

## Reporting issues

Open a [GitHub issue](https://github.com/PaleoLipidRR/TEXAS/issues) with:
- A minimal reproducible example
- Your OS, Python version, and `pip show texas-psm` output
- The full error traceback

## Pull requests

1. Fork the repo and create a branch from `main`.
2. Install in editable mode: `pip install -e .`
3. Make your changes and add tests under `tests/` where relevant.
4. Open a pull request — describe what changed and why.

## Stan models

Stan model files live in `src/TEXAS/stan_models/`. Compiled binaries are cached in `~/.texas/stan_cache/` and are rebuilt automatically when the `.stan` source is newer than the cached copy, so no manual cleanup is needed. To force a rebuild, pass `force=True` to the compiler's `get_model()`.

## Code style

- Python: lint with [ruff](https://docs.astral.sh/ruff/) (config in `pyproject.toml`). CI runs `ruff check` on every pull request; run `pre-commit install` once after cloning to lint and format on commit.
- Comments: only where the *why* is non-obvious — no docblock narration of what the code does.

## Questions

For usage questions, open a [Discussion](https://github.com/PaleoLipidRR/TEXAS/discussions) rather than an issue.
