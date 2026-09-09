# Call map

The [API reference](api.md) lists what each function *is*. This page shows how they
**fit together** — which function calls which, stage by stage, for both halves of the
TEXAS workflow.

Three things you can do with it:

- **Follow a pipeline.** The *Forward calibration* and *Inverse prediction* tabs lay the
  real call graph out in numbered stages, from screening raw data through to a saved
  `.nc` posterior. Click any function for a plain-language explainer, its signature, its
  source location, and clickable lists of what it calls and what calls it.
- **Search the whole package.** The *Every function* tab covers every function and method
  in `src/TEXAS`, grouped by module. Selecting one draws its callers and callees.
- **Spot dead weight.** The *Loose ends* tab lists functions that nothing in the
  repository calls — see [below](#how-the-graph-is-built).

```{raw} html
<p style="margin:1rem 0 0;">
  <a href="_static/callmap.html" target="_blank" rel="noopener"><strong>Open the call map full-page →</strong></a>
</p>
<iframe src="_static/callmap.html"
        title="TEXAS call map — interactive function graph"
        loading="lazy"
        style="width:100%; height:85vh; min-height:640px; border:1px solid rgba(128,128,128,0.35); border-radius:10px; margin:1rem 0;">
</iframe>
```

```{tip}
The map has its own light/dark toggle in the top-right. It follows your operating
system's theme by default, so it may not match this site's theme until you flip it.
```

## How the graph is built

The wires are **not** hand-drawn. `docs/_scripts/build_callmap.py` parses every module
under `src/TEXAS` with Python's `ast` and resolves each call site against the module's
import table:

| Call site | Resolved as |
| --- | --- |
| `helper()` | enclosing function scope → module scope → imports |
| `self.method()` | a method on the enclosing class |
| `self.compiler.get_model()` | the class annotated on `compiler` in `__init__` |
| `sampler.sample()` | the class the local (or module-level) variable was constructed from |
| `Class.method()`, `module.func()` | resolved through the import table |

Anything it cannot resolve with confidence — a dict's `.get()`, a third-party call, a
callable passed in as an argument — is **dropped rather than guessed**. That keeps the
graph trustworthy at the cost of some missing edges, so the handful of genuinely dynamic
calls are re-added by hand in `callmap_content.py` and drawn as **dashed** wires. The
clearest example is `generate_ensemble`, which invokes whichever curve function
`detect_model_and_params` handed it.

Module-level calls (`STAN_BUILD_DIR = _resolve_stan_build_dir()`) are tracked separately
and reported as *"runs at import time"* rather than as edges, since they have no calling
function.

## Loose ends

The *Loose ends* tab flags functions with no caller anywhere — cross-checked against
every `__init__.py` export, the `[project.scripts]` entry points, and a name search
across `notebooks/`, `streamlit_app/` and `tests/`. It separates two very different
cases:

- **Nothing calls these** — no caller in the package *or* outside it. Each carries a
  hand-written note on what it was for and whether it is safe to drop.
- **Public but unexercised** — exported from an `__init__.py`, so users may legitimately
  call them, but nothing in the repository does. No test or notebook would catch a
  regression in these.

Treat it as a shortlist, not a verdict: static analysis cannot see a function reached via
`getattr`, a string-keyed dispatch table, or a user's own script.

## Regenerating

The page is generated, and CI rebuilds it on every docs deploy. To refresh it locally
after changing the package:

```bash
python docs/_scripts/build_callmap.py
```

The build **fails** if `callmap_content.py` references a function that no longer exists,
so renaming or deleting something in `src/TEXAS` surfaces as a build error rather than a
silent gap in the map. Edit `docs/_scripts/callmap_content.py` to add pipeline stages,
explainers, or loose-end notes.
