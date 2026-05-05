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

Stan model files live in `src/TEXAS/stan_models/`. If you modify a `.stan` file, delete the compiled binary (same directory, no extension) so it is recompiled on next use.

## Code style

- Python: follow existing conventions (no strict linter enforced yet).
- Comments: only where the *why* is non-obvious — no docblock narration of what the code does.

## Questions

For usage questions, open a [Discussion](https://github.com/PaleoLipidRR/TEXAS/discussions) rather than an issue.
