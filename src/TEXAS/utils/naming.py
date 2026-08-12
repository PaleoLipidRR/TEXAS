# TEXAS/utils/naming.py
"""
Systematic, CESM-style names for TEXAS calibration artifacts.

WHY
---
The historical names were concatenated *descriptions*, so every axis added
another word and the names grew without bound::

    gen_logi_fixed_hier_crtp_multiv_priorApprox_eiv_boundedT_SST_gdgt23ratio_no3_1.0_scaledRI_cren3.nc   (103 chars)
    MD98-2152_invT_gen_logi_fixed_multiv_unconstrained_boundedT_sst_gdgt23ratio_no3_1.0_scaledRI_cren3_050126_no3_01_direct.nc   (122 chars)

CESM solves this with fixed, dot-delimited *positions*: because position
carries the meaning, each token can be a short mnemonic.  A CESM history file
reads ``b.e21.BHIST.f09_g17.CMIP6-historical.011.cam.h0.TS.185001-201412.nc``
-- model family, version, compset, grid, experiment, member, then component,
stream, field, time range.

TEXAS uses the same idea.  The **case** is the calibration identity::

    tx . v026 . GHEB . sst . ri3 . G23-N10
    |     |      |      |     |      |
    |     |      |      |     |      +-- active predictors
    |     |      |      |     +--------- proxy
    |     |      |      +--------------- target temperature
    |     |      +---------------------- compset (see below)
    |     +----------------------------- calibration/package version
    +----------------------------------- project

and the case is a *directory*, so everything derived from one calibration
lives together and individual filenames stay short::

    tx.v026.GHEB.sst.ri3.G23-N10/
        tx.v026.GHEB.sst.ri3.G23-N10.fwd.nc                  <- forward posterior
        tx.v026.GHEB.sst.ri3.G23-N10.inv.U1482.ud-mod-001.nc <- a reconstruction
        tx.v026.GHEB.sst.ri3.G23-N10.inv.MD98-2152.ud-n01-001.nc

Each leaf repeats the case, the way CESM names data output for its case
(``b.e12.B1850C5CN.f19_g16.iPETM09x.01.pop.h.1901-2000.climo.nc``) rather than
giving it a bare role name. Bare names belong to case *control* files that
never leave the directory; a posterior does leave -- it gets copied around and
published to a flat Zenodo namespace where many ``fwd.nc`` cannot coexist.
The repetition is free: ``<case>/<case>.fwd.nc`` and ``<case>/fwd.nc`` are the
same length, only the separator moves.

THE COMPSET CODE
----------------
Four characters, one per axis, in the manner of CESM's ``BHIST``:

===  =====================  ==========================================
pos  axis                   codes
===  =====================  ==========================================
1    curve family           ``G`` gen_logi_fixed, ``L`` logistic, ``N`` linear
2    training set           ``H`` hier_crtp, ``C`` culmeso, ``J`` culmesocore, ``T`` crtp
3    estimator              ``P`` priorApprox, ``E`` priorApprox+EIV, ``D`` full hierarchical
4    predictor structure    ``U`` univariate, ``A`` additive (beta on mu), ``B`` bounded-T (gamma on T0)
===  =====================  ==========================================

So ``gen_logi_fixed_hier_crtp_multiv_priorApprox_eiv_boundedT`` -> ``GHEB``
and ``gen_logi_fixed_hier_crtp_univ_priorApprox`` -> ``GHPU``.  The
univ/multiv distinction is absorbed into position 4, where it belongs: a
univariate model *is* the no-predictor member of that axis.

Note that the inverse model contributes nothing to the case.  An invT run is
fully determined by the forward posterior it marginalises over, so it is named
as a member *of* that case rather than as a case of its own.

BACKWARD COMPATIBILITY
----------------------
Nothing here renames anything on disk.  :func:`legacy_fwd_name` and
:func:`legacy_invT_name` reproduce the historical names exactly, and
``TEXAS.stan.io.load_posterior`` tries both layouts, so existing caches,
Zenodo downloads, and notebooks that pass long names keep working.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Dict, Optional, Sequence, Union

__all__ = [
    "CaseName",
    "PROJECT",
    "encode_compset",
    "decode_compset",
    "describe_compset",
    "case_from_attrs",
    "parse_case",
    "fwd_relpath",
    "inv_relpath",
    "legacy_fwd_name",
    "legacy_invT_name",
    "default_version",
    "resolve_posterior_path",
    "is_case_id",
    "encode_predictors",
    "decode_predictors",
    "DEFAULT_RUN",
]

PROJECT = "tx"

# --- compset axes ---------------------------------------------------------
# Ordered longest-first where one key is a prefix of another, so that e.g.
# "culmesocore" is never matched as "culmeso".

CURVE_CODES = (
    ("gen_logi_fixed", "G"),
    ("gen_logi", "G"),
    ("logistic", "L"),
    ("linear", "N"),
)

TRAIN_CODES = (
    ("hier_crtp", "H"),
    ("culmesocore", "J"),
    ("culmeso", "C"),
    ("crtp", "T"),
)

# Position 3 is decided by the estimator tokens present in the model name.
EST_CODES = (
    ("priorApprox_eiv", "E"),
    ("priorApprox", "P"),
)
EST_DEFAULT = "D"  # full hierarchical / single-stage

STRUCT_UNIV = "U"
STRUCT_ADDITIVE = "A"
STRUCT_BOUNDED = "B"

_CURVE_LABEL = {"G": "generalized logistic (fixed upper)",
                "L": "standard logistic", "N": "linear"}
_TRAIN_LABEL = {"H": "hierarchical coretop", "C": "culture+mesocosm",
                "J": "culture+mesocosm+coretop", "T": "coretop only"}
_EST_LABEL = {"P": "two-stage prior approximation", "E": "prior approximation + EIV",
              "D": "full hierarchical (single stage)"}
_STRUCT_LABEL = {"U": "univariate (thermal only)",
                 "A": "additive corrections (beta on the response)",
                 "B": "bounded-T corrections (gamma on the inflection point)"}

# --- other axes -----------------------------------------------------------

TEMPTYPE_CODES = {"SST": "sst", "sst": "sst", "thermoT": "thm",
                  "thermot": "thm", "cultureT": "cul", "culturet": "cul"}
TEMPTYPE_DECODE = {"sst": "SST", "thm": "thermoT", "cul": "cultureT"}

# Proxy codes read as: s=scaled, ri=Ring Index, NN=crenarchaeol ring count.
# "cren3" means crenarchaeol counted as 3 rings; cren_rings=4 reproduces the
# RI(0-4) convention of Zhang et al. The bare "ri3" used before 2026-08-11 read
# like "ring index variant 3", which is not what it means.
#
# TEXRI_cren3 previously shared the "ri3" code with scaledRI_cren3, so two
# distinct proxies collapsed onto one case id and one would silently overwrite
# the other. It now has its own code.
PROXY_CODES = {"scaledRI_cren3": "sri03", "scaledRI_cren4": "sri04",
               "scaledRI": "sri", "TEX86": "tex", "TEXRI_cren3": "tri03"}
PROXY_DECODE = {"sri03": "scaledRI_cren3", "sri04": "scaledRI_cren4",
                "sri": "scaledRI", "tex": "TEX86", "tri03": "TEXRI_cren3",
                # pre-2026-08-11 codes, so existing case ids still parse
                "ri3": "scaledRI_cren3", "ri4": "scaledRI_cren4",
                "ri": "scaledRI"}

CONSTRAINT_CODES = {"unconstrained": "u", "hard_constraint": "h",
                    "truncated_prior": "t", "reparameterized": "r", "soft": "s"}
CONSTRAINT_DECODE = {v: k for k, v in CONSTRAINT_CODES.items()}

KIND_CODES = {"direct": "d", "ensemble": "e"}
KIND_DECODE = {v: k for k, v in KIND_CODES.items()}

# "zero predictors". Kept as an explicit position rather than omitted, the way
# CESM names an absent component explicitly (SGLC = stub glacier) instead of
# dropping the field -- fixed positions are what make the id parseable. Note it
# is partly redundant with the compset's 4th character (U = univariate); the
# position exists so the predictor axis is always readable without decoding the
# compset.
NO_PREDICTORS = "p0"

#: Pre-2026-08-11 spelling, still accepted when parsing existing case ids.
LEGACY_NO_PREDICTORS = "none"

DEFAULT_RUN = "001"

_CASE_RE = re.compile(
    r"^(?P<project>[a-z]{2,4})\."
    r"(?P<version>v[0-9a-z]+)\."
    r"(?P<compset>[A-Z]{4})\."
    r"(?P<temptype>[a-z]{2,4})\."
    r"(?P<proxy>[a-z0-9]{2,5})\."
    r"(?P<predictors>[A-Za-z0-9-]+)"
    r"(?:\.(?P<run>[A-Za-z0-9-]+))?$"
)


def default_version() -> str:
    """``v`` + the package version with separators dropped: 0.2.6 -> ``v026``."""
    try:
        from .. import __version__ as v
    except Exception:  # pragma: no cover - package metadata unavailable
        return "v000"
    parts = re.findall(r"\d+", str(v))[:3]
    return "v" + "".join(parts) if parts else "v000"


# ---------------------------------------------------------------------------
# Compset encoding
# ---------------------------------------------------------------------------

def encode_compset(stan_model_name: str) -> str:
    """
    Collapse a long Stan model name into the four-character compset code.

    >>> encode_compset("gen_logi_fixed_hier_crtp_multiv_priorApprox_eiv_boundedT")
    'GHEB'
    >>> encode_compset("gen_logi_fixed_hier_crtp_univ_priorApprox")
    'GHPU'
    >>> encode_compset("gen_logi_fixed_culmesocore")
    'GJDU'
    """
    if not stan_model_name:
        raise ValueError("stan_model_name is empty; cannot build a compset code.")
    name = str(stan_model_name)
    # An inverse model name never defines a case -- strip the marker so callers
    # that pass one by mistake still get the curve axis right.
    stem = name[len("invT_"):] if name.startswith("invT_") else name

    curve = _first_code(stem, CURVE_CODES)
    if curve is None:
        raise ValueError(
            f"Unrecognised curve family in {stan_model_name!r}. "
            f"Expected one of: {[k for k, _ in CURVE_CODES]}"
        )

    train = _first_code(stem, TRAIN_CODES)
    if train is None:
        # Inverse models carry no training set; the case comes from the forward
        # posterior. Fall back to coretop, the only set the invT models target.
        train = "T"

    est = _first_code(stem, EST_CODES) or EST_DEFAULT

    if "boundedT" in stem:
        struct = STRUCT_BOUNDED
    elif "multiv" in stem:
        struct = STRUCT_ADDITIVE
    elif "univ" in stem:
        struct = STRUCT_UNIV
    else:
        # Models with no predictor axis in the name (culmeso, culmesocore, ...)
        # are thermal-only by construction.
        struct = STRUCT_UNIV

    return f"{curve}{train}{est}{struct}"


def _first_code(text: str, table: Sequence) -> Optional[str]:
    for token, code in table:
        if token in text:
            return code
    return None


def decode_compset(code: str) -> Dict[str, str]:
    """Expand a compset code into its four axis labels."""
    code = str(code).strip().upper()
    if len(code) != 4:
        raise ValueError(f"A compset code is exactly 4 characters; got {code!r}")
    c, t, e, s = code
    for char, table, axis in ((c, _CURVE_LABEL, "curve"), (t, _TRAIN_LABEL, "training set"),
                              (e, _EST_LABEL, "estimator"), (s, _STRUCT_LABEL, "structure")):
        if char not in table:
            raise ValueError(f"Unknown {axis} code {char!r} in compset {code!r}")
    return {"curve": _CURVE_LABEL[c], "training_set": _TRAIN_LABEL[t],
            "estimator": _EST_LABEL[e], "structure": _STRUCT_LABEL[s]}


def describe_compset(code: str) -> str:
    """One-line human-readable expansion, for logs and figure captions."""
    d = decode_compset(code)
    return (f"{code}: {d['curve']}, {d['training_set']}, "
            f"{d['estimator']}, {d['structure']}")


# ---------------------------------------------------------------------------
# Predictor token
# ---------------------------------------------------------------------------

def encode_predictors(use_gdgt23ratio: bool = False,
                      use_no3: bool = False,
                      no3_cutoff: Optional[float] = None) -> str:
    """
    ``G23`` for the GDGT-2/3 ratio, ``N`` + cutoff x10 for nitrate.

    >>> encode_predictors(True, True, 1.0)
    'G23-N10'
    >>> encode_predictors(True, False)
    'G23'
    >>> encode_predictors()
    'none'
    """
    parts = []
    if use_gdgt23ratio:
        parts.append("G23")
    if use_no3:
        if no3_cutoff is None:
            raise ValueError("no3_cutoff is required when use_no3 is set.")
        parts.append(f"N{int(round(float(no3_cutoff) * 10)):02d}")
    return "-".join(parts) if parts else NO_PREDICTORS


def decode_predictors(token: str) -> Dict[str, Any]:
    """Inverse of :func:`encode_predictors`."""
    out = {"use_gdgt23ratio": False, "use_no3": False, "no3_cutoff": None}
    if not token or token in (NO_PREDICTORS, LEGACY_NO_PREDICTORS):
        return out
    for part in str(token).split("-"):
        if part == "G23":
            out["use_gdgt23ratio"] = True
        elif re.fullmatch(r"N\d{2}", part):
            out["use_no3"] = True
            out["no3_cutoff"] = int(part[1:]) / 10.0
        elif part:
            raise ValueError(f"Unrecognised predictor token {part!r} in {token!r}")
    return out


# ---------------------------------------------------------------------------
# The case
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CaseName:
    """
    One calibration identity: ``tx.v026.GHEB.sst.ri3.G23-N10.001``.

    The trailing *run* position is CESM's ensemble-member field.  It keeps two
    refits of the same configuration -- a date-stamped rerun, a seed sweep, a
    reviewer-requested repeat -- from colliding on one name.  It defaults to
    ``001``, so a single run of a configuration reads cleanly.
    """

    compset: str
    temptype: str
    proxy: str
    predictors: str = NO_PREDICTORS
    version: str = ""
    project: str = PROJECT
    run: str = DEFAULT_RUN

    def __post_init__(self):
        if not self.version:
            object.__setattr__(self, "version", default_version())
        object.__setattr__(self, "compset", self.compset.upper())
        object.__setattr__(self, "run", slug(self.run) or DEFAULT_RUN)
        decode_compset(self.compset)  # validate eagerly

    def __str__(self) -> str:
        return ".".join([self.project, self.version, self.compset,
                         self.temptype, self.proxy, self.predictors, self.run])

    # -- convenience ------------------------------------------------------
    @property
    def temptype_full(self) -> str:
        return TEMPTYPE_DECODE.get(self.temptype, self.temptype)

    @property
    def proxy_full(self) -> str:
        return PROXY_DECODE.get(self.proxy, self.proxy)

    def describe(self) -> str:
        d = decode_compset(self.compset)
        p = decode_predictors(self.predictors)
        preds = []
        if p["use_gdgt23ratio"]:
            preds.append("GDGT-2/3 ratio")
        if p["use_no3"]:
            preds.append(f"NO3 (cutoff {p['no3_cutoff']})")
        return (
            f"{self}\n"
            f"  curve        : {d['curve']}\n"
            f"  training set : {d['training_set']}\n"
            f"  estimator    : {d['estimator']}\n"
            f"  structure    : {d['structure']}\n"
            f"  target       : {self.temptype_full}\n"
            f"  proxy        : {self.proxy_full}\n"
            f"  predictors   : {', '.join(preds) if preds else 'none (thermal only)'}"
        )

    def with_variant(self, structure: str) -> "CaseName":
        """Same case with position 4 swapped -- the additive/bounded-T switch."""
        code = structure.upper()[0]
        if code not in _STRUCT_LABEL:
            raise ValueError(f"structure must be one of {sorted(_STRUCT_LABEL)}")
        return replace(self, compset=self.compset[:3] + code)


def case_from_attrs(attrs: Dict[str, Any], *, version: Optional[str] = None,
                    run: str = DEFAULT_RUN) -> CaseName:
    """
    Build a :class:`CaseName` from a posterior's ``.attrs``.

    Reads ``stan_model_name``, ``temptype``, ``proxy_name``,
    ``use_gdgt23ratio``, ``use_no3`` and ``no3_cutoff`` -- exactly the fields
    ``save_posterior`` already relies on.
    """
    model = attrs.get("stan_model_name") or ""
    temptype = str(attrs.get("temptype", "") or "")
    proxy = str(attrs.get("proxy_name", "") or "")

    tt = TEMPTYPE_CODES.get(temptype) or TEMPTYPE_CODES.get(temptype.lower())
    if tt is None:
        tt = re.sub(r"[^a-z0-9]", "", temptype.lower())[:4] or "unk"

    px = PROXY_CODES.get(proxy)
    if px is None:
        px = re.sub(r"[^a-z0-9]", "", proxy.lower())[:5] or "unk"

    return CaseName(
        compset=encode_compset(model),
        temptype=tt,
        proxy=px,
        predictors=encode_predictors(
            bool(int(attrs.get("use_gdgt23ratio", 0) or 0)),
            bool(int(attrs.get("use_no3", 0) or 0)),
            attrs.get("no3_cutoff"),
        ),
        version=version or default_version(),
        run=run,
    )


def parse_case(text: str) -> CaseName:
    """Parse ``tx.v026.GHEB.sst.ri3.G23-N10.001`` back into a :class:`CaseName`.

    The run position may be omitted, in which case it defaults to ``001``.
    """
    s = str(text).strip().rstrip("/")
    if s.endswith(".nc"):
        s = s[:-3]
    m = _CASE_RE.match(s)
    if not m:
        raise ValueError(
            f"{text!r} is not a case id. Expected "
            f"<project>.<version>.<COMPSET>.<temptype>.<proxy>.<predictors>[.<run>], "
            f"e.g. 'tx.v026.GHEB.sst.ri3.G23-N10.001'."
        )
    g = m.groupdict()
    return CaseName(compset=g["compset"], temptype=g["temptype"], proxy=g["proxy"],
                    predictors=g["predictors"], version=g["version"],
                    project=g["project"], run=g["run"] or DEFAULT_RUN)


def is_case_id(text: str) -> bool:
    """True when *text* looks like a case id (cheap guard for dual-read)."""
    try:
        parse_case(text)
        return True
    except ValueError:
        return False


# ---------------------------------------------------------------------------
# Paths within a case
# ---------------------------------------------------------------------------

def fwd_relpath(case: Union[CaseName, str]) -> Path:
    """
    ``<case>/<case>.fwd.nc`` -- the forward posterior of a case.

    The case is repeated in the leaf on purpose. CESM names data output for its
    case (``b.e12.B1850C5CN.f19_g16.iPETM09x.01.pop.h.1901-2000.climo.nc``) and
    reserves bare names for case *control* files that never leave the case
    directory. A posterior does leave: it is copied around and, decisively,
    published to a Zenodo record with a **flat** namespace, where fifteen files
    named ``fwd.nc`` cannot coexist. Repeating the case costs nothing -- the
    full path is the same length either way, only the separator moves.

    >>> str(fwd_relpath("tx.v026.GHEB.sst.ri3.G23-N10.001"))
    'tx.v026.GHEB.sst.ri3.G23-N10.001/tx.v026.GHEB.sst.ri3.G23-N10.001.fwd.nc'
    """
    c = str(case)
    return Path(c) / f"{c}.fwd.nc"


#: Pre-2026-08-11 leaf name, kept so existing caches still resolve.
LEGACY_FWD_LEAF = "fwd.nc"


def fwd_leaf_candidates(case: Union[CaseName, str]) -> tuple:
    """Leaf names to try inside a case dir, current scheme first."""
    return (f"{case}.fwd.nc", LEGACY_FWD_LEAF)


def inv_relpath(
    case: Union[CaseName, str],
    site: str,
    *,
    constraint: str = "unconstrained",
    kind: str = "direct",
    scenario: Optional[str] = None,
    run: Union[int, str] = 1,
) -> Path:
    """
    ``<case>/<case>.inv.<site>.<constraint><kind>[-<scenario>]-<NNN>.nc``

    The case is repeated in the leaf for the same reason as in
    :func:`fwd_relpath` -- a reconstruction that is copied out of its case
    directory must still say which calibration it came from.

    >>> p = inv_relpath("tx.v026.GHEB.sst.ri3.G23-N10", "U1482", scenario="mod")
    >>> p.name
    'tx.v026.GHEB.sst.ri3.G23-N10.inv.U1482.ud-mod-001.nc'
    """
    c = CONSTRAINT_CODES.get(constraint)
    if c is None:
        raise ValueError(f"constraint must be one of {sorted(CONSTRAINT_CODES)}")
    k = KIND_CODES.get(kind)
    if k is None:
        raise ValueError(f"kind must be one of {sorted(KIND_CODES)}")

    run_str = f"{int(run):03d}" if str(run).isdigit() else slug(run)
    parts = [f"{c}{k}"]
    if scenario:
        parts.append(slug(scenario))
    parts.append(run_str)
    c = str(case)
    return Path(c) / f"{c}.inv.{slug(site)}.{'-'.join(parts)}.nc"


def slug(x: Any) -> str:
    """Filename-safe token: spaces to hyphens, everything exotic dropped."""
    return re.sub(r"[^A-Za-z0-9._-]+", "", str(x).strip().replace(" ", "-"))


# ---------------------------------------------------------------------------
# Legacy names -- reproduced exactly, for dual-read fallback
# ---------------------------------------------------------------------------

def resolve_posterior_path(name: str, indir: Union[str, Path]) -> Optional[Path]:
    """
    Find a forward posterior under *indir* by either naming scheme.

    Resolution order, cheapest first:

    1. ``indir/<name>.nc``                  -- historical flat layout, exact hit
    2. ``indir/<name>/<name>.fwd.nc``       -- case-directory layout, exact hit
    3. ``indir/<name>/fwd.nc``              -- case dirs written before
       2026-08-11, when the leaf was a bare ``fwd.nc``
    4. *name* is a case id           -- scan flat ``.nc`` files and match the
       case computed from each file's attrs
    5. *name* is a legacy long name  -- scan case directories and match the
       legacy name computed from each forward posterior's attrs

    Steps 4 and 5 open files, so they run only when the exact lookups miss.
    Returns ``None`` when nothing matches, leaving the caller to raise.
    """
    indir = Path(indir)

    flat = indir / f"{name}.nc"
    if flat.exists():
        return flat

    for leaf in fwd_leaf_candidates(name):
        cased = indir / name / leaf
        if cased.exists():
            return cased

    if not indir.is_dir():
        return None

    import xarray as xr

    if is_case_id(name):
        want = str(parse_case(name))
        for f in sorted(indir.glob("*.nc")):
            try:
                with xr.open_dataset(f) as ds:
                    attrs = dict(ds.attrs)
            except Exception:
                continue
            try:
                # A date-stamped legacy file carries its stamp in the filename,
                # not in attrs, so compare on the run-free part of the case too.
                got = case_from_attrs(attrs)
            except Exception:
                continue
            if str(got) == want or str(replace(got, run=parse_case(name).run)) == want:
                return f
        return None

    # name looks like a legacy long name -> hunt through the case directories
    for d in sorted(p for p in indir.iterdir() if p.is_dir()):
        fwd = next((d / leaf for leaf in fwd_leaf_candidates(d.name)
                    if (d / leaf).exists()), None)
        if fwd is None:
            continue
        try:
            with xr.open_dataset(fwd) as ds:
                attrs = dict(ds.attrs)
        except Exception:
            continue
        try:
            if legacy_fwd_name(attrs) == name:
                return fwd
        except Exception:
            continue
    return None


def legacy_fwd_name(attrs: Dict[str, Any], filename_suffix: str = "") -> str:
    """
    The historical forward name:
    ``{model}_{temptype}[_gdgt23ratio][_no3_{cutoff}][_{proxy}]{suffix}``.
    """
    name = attrs.get("stan_model_name", "unknown_model")
    ttype = str(attrs.get("temptype", "unknown"))
    if attrs.get("use_gdgt23ratio", 0):
        ttype += "_gdgt23ratio"
    if attrs.get("use_no3", 0):
        cutoff = attrs.get("no3_cutoff")
        if cutoff is None:
            raise ValueError("no3_cutoff must be set when use_no3=1")
        ttype += f"_no3_{cutoff}"
    proxy = attrs.get("proxy_name", "") or ""
    proxy_tag = f"_{proxy}" if proxy and proxy != "unknown" else ""
    if filename_suffix:
        filename_suffix = f"_{filename_suffix.strip('_')}"
    return f"{name}_{ttype}{proxy_tag}{filename_suffix}"


def legacy_invT_name(
    site: str,
    stan_model_name: str,
    temptype: str,
    *,
    proxy_name: str = "",
    use_gdgt23ratio: bool = False,
    use_no3: bool = False,
    no3_cutoff: Optional[float] = None,
    tags: Optional[Union[str, Sequence[str]]] = None,
) -> str:
    """The historical invT name, matching ``io._generate_filename_base``."""
    clean = stan_model_name.replace("_marginal", "")
    kind = "direct" if "marginal" in stan_model_name else "ensemble"

    parts = [temptype]
    if use_gdgt23ratio:
        parts.append("gdgt23ratio")
    if use_no3:
        if no3_cutoff is None:
            raise ValueError("no3_cutoff must be set when use_no3=1")
        parts.append(f"no3_{no3_cutoff}")
    temptype_str = "_".join(parts)

    proxy_segment = f"_{slug(proxy_name)}" if proxy_name and proxy_name != "unknown" else ""

    tag_segment = ""
    if tags:
        tag_list = [tags] if isinstance(tags, str) else list(tags)
        joined = "+".join(slug(t) for t in tag_list if t)
        if joined:
            tag_segment = f"_{joined}"

    return f"{slug(site)}_{clean}_{temptype_str}{proxy_segment}{tag_segment}_{kind}"
