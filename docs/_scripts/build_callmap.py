#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Generate the interactive TEXAS call map -> docs/_static/callmap.html.

The call graph is extracted from ``src/TEXAS`` with an import-aware AST pass,
so the wires shown on the page are real static calls rather than a hand-drawn
diagram that drifts out of date.  Curated pipeline stages and the hand-written
explainers live in ``callmap_content.py``; the page shell lives in
``callmap_template.html``.

Run it after changing the package (CI does this before ``jupyter-book build``):

    python docs/_scripts/build_callmap.py

Resolution rules, deliberately conservative — a missed edge is better than a
wrong one:

* bare ``name()``      -> enclosing-function scope, then module scope, then imports
* ``self.method()``    -> the enclosing class
* ``self.attr.meth()`` -> the class annotated on ``attr`` in ``__init__``
* ``Class.method()`` / ``module.func()`` -> resolved through the import table
* anything else (dict ``.get()``, third-party calls, callables passed as
  arguments) is dropped.  Genuinely dynamic dispatch is re-added by hand in
  ``callmap_content.py`` and drawn dashed.
"""
from __future__ import annotations

import ast
import json
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DOCS = HERE.parent
REPO = DOCS.parent
SRC = REPO / "src" / "TEXAS"
DEFAULT_OUT = DOCS / "_static" / "callmap.html"

sys.path.insert(0, str(HERE))
import callmap_content as content  # noqa: E402

# Method names common enough on builtins that an unqualified match is unsafe.
STDLIB_NOISE = {"get", "append", "keys", "items", "values", "update", "format",
                "join", "split", "strip", "copy", "pop", "sort", "add"}

funcs: dict[str, dict] = {}
classes: dict[str, dict] = {}
mod_imports: dict[str, dict[str, str]] = {}
mod_trees: dict[str, ast.Module] = {}
# callee qualname -> modules whose top level calls it while being imported
import_time: dict[str, set[str]] = {}


class Collector(ast.NodeVisitor):
    """Record every def/class with its qualified name, signature and docstring."""

    def __init__(self, mod: str):
        self.mod = mod
        self.stack: list[str] = []

    @staticmethod
    def _sig(node) -> str:
        a = node.args
        parts = []
        for arg in getattr(a, "posonlyargs", []) + a.args:
            parts.append(arg.arg + (f": {ast.unparse(arg.annotation)}" if arg.annotation else ""))
        if a.vararg:
            parts.append("*" + a.vararg.arg)
        elif a.kwonlyargs:
            parts.append("*")
        for arg in a.kwonlyargs:
            parts.append(arg.arg + (f": {ast.unparse(arg.annotation)}" if arg.annotation else ""))
        if a.kwarg:
            parts.append("**" + a.kwarg.arg)
        ret = f" -> {ast.unparse(node.returns)}" if node.returns else ""
        return f"{node.name}({', '.join(parts)}){ret}"

    def _visit_func(self, node):
        scope = ".".join(self.stack)
        qual = f"{self.mod}.{scope + '.' if scope else ''}{node.name}"
        cls = None
        for i, s in enumerate(self.stack):
            if f"{self.mod}.{'.'.join(self.stack[:i + 1])}" in classes:
                cls = s
        funcs[qual] = {
            "qual": qual, "name": node.name, "module": self.mod, "cls": cls,
            "nested_in": scope if (scope and not cls) else None,
            "lineno": node.lineno, "endline": getattr(node, "end_lineno", node.lineno),
            "doc": ast.get_docstring(node) or "", "sig": self._sig(node), "node": node,
        }
        self.stack.append(node.name)
        for child in node.body:
            self.visit(child)
        self.stack.pop()

    visit_FunctionDef = _visit_func
    visit_AsyncFunctionDef = _visit_func

    def visit_ClassDef(self, node):
        scope = ".".join(self.stack)
        qual = f"{self.mod}.{scope + '.' if scope else ''}{node.name}"
        classes[qual] = {
            "qual": qual, "name": node.name, "module": self.mod,
            "doc": ast.get_docstring(node) or "", "lineno": node.lineno,
        }
        self.stack.append(node.name)
        for child in node.body:
            self.visit(child)
        self.stack.pop()


def collect() -> None:
    for p in sorted(SRC.rglob("*.py")):
        mod = str(p.relative_to(SRC.parent).with_suffix("")).replace(os.sep, ".")
        tree = ast.parse(p.read_text(encoding="utf-8"))
        imports: dict[str, str] = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                base = node.module or ""
                if node.level:                      # relative import
                    pkg = mod.rsplit(".", node.level)[0]
                    base = f"{pkg}.{node.module}" if node.module else pkg
                for al in node.names:
                    imports[al.asname or al.name] = f"{base}.{al.name}"
            elif isinstance(node, ast.Import):
                for al in node.names:
                    imports[al.asname or al.name.split(".")[0]] = al.name
        mod_imports[mod] = imports
        mod_trees[mod] = tree
        Collector(mod).visit(tree)


def self_attr_types() -> dict[tuple[str, str, str], str]:
    """Map (module, class, self-attribute) -> class qualname, via __init__ annotations."""
    out: dict[tuple[str, str, str], str] = {}
    for info in funcs.values():
        if info["name"] != "__init__" or not info["cls"]:
            continue
        mod, cls, node = info["module"], info["cls"], info["node"]
        a = node.args
        ann = {arg.arg: ast.unparse(arg.annotation)
               for arg in getattr(a, "posonlyargs", []) + a.args + a.kwonlyargs
               if arg.annotation}
        for sub in ast.walk(node):
            if not isinstance(sub, ast.Assign) or not isinstance(sub.value, ast.Name):
                continue
            t = ann.get(sub.value.id)
            if not t:
                continue
            for tgt in sub.targets:
                if (isinstance(tgt, ast.Attribute) and isinstance(tgt.value, ast.Name)
                        and tgt.value.id == "self"):
                    for cand in (f"{mod}.{t}", mod_imports[mod].get(t, "")):
                        if cand in classes:
                            out[(mod, cls, tgt.attr)] = cand
    return out


def resolve_edges() -> list[tuple[str, str]]:
    selfattr = self_attr_types()

    def resolve_name(name: str, qual: str):
        mod = funcs[qual]["module"]
        parts = qual.split(".")
        for i in range(len(parts), len(mod.split(".")), -1):   # enclosing closures
            cand = ".".join(parts[:i]) + "." + name
            if cand in funcs:
                return cand
        if f"{mod}.{name}" in funcs:
            return f"{mod}.{name}"
        tgt = mod_imports[mod].get(name)
        if tgt and tgt in funcs:
            return tgt
        for cbase in (tgt, f"{mod}.{name}"):                   # constructor call
            if cbase in classes and f"{cbase}.__init__" in funcs:
                return f"{cbase}.__init__"
        return None

    def var_types(body, scope_qual: str) -> dict[str, str]:
        """`x = SomeTexasClass(...)` in this scope -> {"x": class qualname}.

        Keeps `model.sample()` (a third-party CmdStanModel) from being confused
        with `sampler.sample()` (ours) — only TEXAS constructors bind a name.
        """
        out: dict[str, str] = {}
        for n in body:
            if not isinstance(n, ast.Assign) or not isinstance(n.value, ast.Call):
                continue
            f = n.value.func
            if not isinstance(f, ast.Name):
                continue
            hit = resolve_name(f.id, scope_qual)
            if not (hit and hit.endswith(".__init__")):
                continue
            for t in n.targets:
                if isinstance(t, ast.Name):
                    out[t.id] = hit[: -len(".__init__")]
        return out

    module_vars: dict[str, dict[str, str]] = {}

    def resolve_attr(attr: str, base, qual: str, local: dict[str, str] | None = None):
        info = funcs[qual]
        mod, cls = info["module"], info["cls"]
        if base == "self" and cls:
            cand = f"{mod}.{cls}.{attr}"
            return cand if cand in funcs else None
        if base and base.startswith("self.") and cls:
            owner = selfattr.get((mod, cls, base[5:]))
            cand = f"{owner}.{attr}" if owner else None
            return cand if cand and cand in funcs else None
        if not base:
            return None
        # a local or module-level variable holding a TEXAS instance
        owner = (local or {}).get(base) or module_vars.get(mod, {}).get(base)
        if owner:
            cand = f"{owner}.{attr}"
            return cand if cand in funcs else None
        for cbase in (f"{mod}.{base}", mod_imports[mod].get(base, "")):
            if cbase in classes:
                cand = f"{cbase}.{attr}"
                return cand if cand in funcs else None
        tgt = mod_imports[mod].get(base)
        if tgt and f"{tgt}.{attr}" in funcs:
            return f"{tgt}.{attr}"
        return None

    def calls_in(body) -> list[ast.Call]:
        """Every Call in `body`, not descending into nested defs (own nodes)."""
        todo, out = list(body), []
        while todo:
            n = todo.pop()
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            if isinstance(n, ast.Call):
                out.append(n)
            todo.extend(ast.iter_child_nodes(n))
        return out

    def target_of(call: ast.Call, qual: str, local: dict[str, str] | None = None):
        f = call.func
        if isinstance(f, ast.Name):
            return resolve_name(f.id, qual)
        if isinstance(f, ast.Attribute) and f.attr not in STDLIB_NOISE:
            if isinstance(f.value, ast.Name):
                base = f.value.id
            elif isinstance(f.value, ast.Attribute):
                base = ast.unparse(f.value)
            else:
                base = None
            return resolve_attr(f.attr, base, qual, local)
        return None

    # Module-level instances (e.g. _default_sampler = StanSampler(...)) must be
    # known before function bodies that use them are resolved.
    for mod, tree in mod_trees.items():
        pseudo = f"{mod}.<module>"
        funcs[pseudo] = {"module": mod, "cls": None, "nested_in": None}
        module_vars[mod] = var_types(tree.body, pseudo)
        del funcs[pseudo]

    seen: set[tuple[str, str]] = set()
    for qual, info in funcs.items():
        body = info["node"].body
        local = var_types(body, qual)
        for c in calls_in(body):
            tgt = target_of(c, qual, local)
            if tgt and tgt != qual:
                seen.add((qual, tgt))

    # Module top level runs on import — e.g. STAN_BUILD_DIR = _resolve_stan_build_dir().
    # These are real calls but have no calling *function*, so they are tracked
    # separately rather than as graph edges.
    for mod, tree in mod_trees.items():
        pseudo = f"{mod}.<module>"
        funcs[pseudo] = {"module": mod, "cls": None, "nested_in": None}
        for c in calls_in(tree.body):
            tgt = target_of(c, pseudo)
            if tgt:
                import_time.setdefault(tgt, set()).add(mod)
        del funcs[pseudo]

    return sorted(seen)


def exported_names() -> set[str]:
    """Names re-exported by any __init__.py (package or sub-package)."""
    out: set[str] = set()
    for p in (SRC).rglob("__init__.py"):
        tree = ast.parse(p.read_text(encoding="utf-8"))
        for n in ast.walk(tree):
            if isinstance(n, (ast.Import, ast.ImportFrom)):
                out.update(al.asname or al.name for al in n.names)
            elif isinstance(n, ast.Assign):
                for t in n.targets:
                    if isinstance(t, ast.Name) and t.id == "__all__":
                        try:
                            out.update(ast.literal_eval(n.value))
                        except (ValueError, SyntaxError):
                            pass
    return out


def cli_entry_points() -> set[str]:
    pt = REPO / "pyproject.toml"
    if not pt.exists():
        return set()
    return {f"TEXAS.{m[1]}.{m[2]}" for m in
            re.finditer(r'=\s*"TEXAS\.([\w.]+):(\w+)"', pt.read_text(encoding="utf-8"))}


def caller_corpus() -> dict[str, str]:
    """Text of everything outside the package that could call into it."""
    corpus: dict[str, str] = {}
    for sub, pats in (("notebooks", ("**/*.ipynb", "**/*.py")),
                      ("streamlit_app", ("**/*.py",)),
                      ("tests", ("**/*.py",))):
        d = REPO / sub
        if not d.exists():
            continue
        for pat in pats:
            for f in d.glob(pat):
                if {"_build", ".ipynb_checkpoints", "__pycache__"} & set(f.parts):
                    continue
                try:
                    corpus[f.relative_to(REPO).as_posix()] = f.read_text(
                        encoding="utf-8", errors="ignore")
                except OSError:
                    pass
    return corpus


def classify_reach(nodes_in: dict[str, set[str]]) -> dict[str, dict]:
    """How is each function reached? Drives the 'Loose ends' view."""
    exported, cli, corpus = exported_names(), cli_entry_points(), caller_corpus()
    dupes: dict[str, list[str]] = {}
    for q, i in funcs.items():
        if not i["nested_in"]:
            dupes.setdefault(i["name"], []).append(q)

    reach: dict[str, dict] = {}
    for q, i in funcs.items():
        name = i["name"]
        internal = sorted(nodes_in.get(q, ()))
        imports = sorted(import_time.get(q, ()))
        # Where outside the package is this name called?
        pat = re.compile(r"\b" + re.escape(name) + r"\s*\(")
        ext = sorted({path.split("/")[0] for path, txt in corpus.items() if pat.search(txt)})

        if name.startswith("__") and name.endswith("__"):
            kind = "constructor" if name == "__init__" else "runtime"
        elif i["nested_in"]:
            kind = "closure"
        elif internal:
            kind = "internal"
        elif imports:
            kind = "import-time"
        elif q in cli:
            kind = "cli"
        elif ext:
            kind = "external"
        elif name in exported:
            kind = "exported-only"
        else:
            kind = "unreferenced"
        entry = {"k": kind}
        if ext:
            entry["ext"] = ext
        if imports:
            entry["imp"] = [short(m) for m in imports]
        if name in exported:
            entry["pub"] = 1
        twins = [short(x) for x in dupes.get(name, []) if x != q]
        if twins:
            entry["dup"] = twins
        reach[short(q)] = entry
    return reach


def short(q: str) -> str:
    return q[len("TEXAS."):] if q.startswith("TEXAS.") else q


def trim_doc(d: str, limit: int = 1400) -> str:
    if not d:
        return ""
    d = d.replace("\r\n", "\n").strip()
    return d if len(d) <= limit else d[:limit].rsplit("\n", 1)[0] + "\n…"


def main() -> int:
    collect()
    edge_pairs = resolve_edges()

    # Every qualname referenced by the curated content must exist, or the page
    # would silently render a hole. Fail loudly instead.
    problems = []
    for pipe in content.PIPELINES:
        for st in pipe["stages"]:
            problems += [f"{pipe['id']} / {st['name']}: {n}"
                         for n in st["nodes"] if "TEXAS." + n not in funcs]
        for a, b, _ in pipe.get("dynamic", []):
            problems += [f"{pipe['id']} / dynamic: {n}"
                         for n in (a, b) if "TEXAS." + n not in funcs]
    problems += [f"EXPLAIN: {k}" for k in content.EXPLAIN if "TEXAS." + k not in funcs]
    if problems:
        print("Curated content references functions that no longer exist:", file=sys.stderr)
        for p in problems:
            print("  -", p, file=sys.stderr)
        print("\nUpdate docs/_scripts/callmap_content.py.", file=sys.stderr)
        return 1

    nodes = {}
    for q, i in funcs.items():
        s = short(q)
        nodes[s] = {
            "n": i["name"], "m": short(i["module"]), "c": i["cls"], "nest": i["nested_in"],
            "l": i["lineno"], "e": i["endline"], "sig": i["sig"],
            "doc": trim_doc(i["doc"]), "x": content.EXPLAIN.get(s, ""),
            "priv": i["name"].startswith("_") and i["name"] != "__init__",
            "path": "src/" + i["module"].replace(".", "/") + ".py",
        }
    edges = [[short(a), short(b)] for a, b in edge_pairs]

    nodes_in: dict[str, set[str]] = {}
    for a, b in edge_pairs:
        nodes_in.setdefault(b, set()).add(a)
    reach = classify_reach(nodes_in)

    data = {
        "nodes": nodes,
        "edges": edges,
        "reach": reach,
        "pipelines": content.PIPELINES,
        "notes": content.LOOSE_ENDS,
        "stats": {"functions": len(nodes), "edges": len(edges),
                  "modules": len({v["m"] for v in nodes.values()}),
                  "classes": len(classes)},
    }
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    if "</script" in payload:                # would break out of the <script> block
        print("Payload contains a closing script tag.", file=sys.stderr)
        return 1

    tpl = (HERE / "callmap_template.html").read_text(encoding="utf-8")
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(tpl.replace("/*__DATA__*/null", payload), encoding="utf-8")
    print(f"{out.relative_to(REPO)}: {len(nodes)} functions, {len(edges)} static calls, "
          f"{len(content.EXPLAIN)} explainers ({out.stat().st_size / 1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
