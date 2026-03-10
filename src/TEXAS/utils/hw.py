# DEPRECATED: Only used by stan/auto.py (also deprecated). Kept for reference only.
# TEXAS/utils/hw.py
from __future__ import annotations
import os, shutil, subprocess, logging

log = logging.getLogger(__name__)

def _clinfo_platforms() -> int | None:
    """
    Returns the number of OpenCL platforms reported by `clinfo`,
    or None if `clinfo` is unavailable / errors.
    """
    if shutil.which("clinfo") is None:
        return None
    try:
        out = subprocess.check_output(["clinfo"], text=True, timeout=3)
        for line in out.splitlines():
            if line.strip().startswith("Number of platforms"):
                # line format: Number of platforms <whitespace> <int>
                parts = line.split()
                n = int(parts[-1])
                return n
        return None
    except Exception as e:
        log.debug("clinfo probe failed: %r", e)
        return None

def detect_opencl_available() -> bool:
    """
    Decide if we should enable Stan OpenCL.

    Precedence:
    1) ENV TEXAS_USE_OPENCL = '1'/'true' or '0'/'false'
    2) If clinfo says >=1 platforms → True
    3) Otherwise False
    """
    env = os.getenv("TEXAS_USE_OPENCL")
    if env is not None:
        env = env.strip().lower()
        if env in {"1", "true", "yes", "on"}:
            log.info("TEXAS_USE_OPENCL=1 → forcing OpenCL ON")
            return True
        if env in {"0", "false", "no", "off"}:
            log.info("TEXAS_USE_OPENCL=0 → forcing OpenCL OFF")
            return False
        log.warning("Unrecognized TEXAS_USE_OPENCL=%r; falling back to auto-detect.", env)

    nplat = _clinfo_platforms()
    if nplat is None:
        log.info("OpenCL auto-detect: clinfo unavailable → treating as no OpenCL")
        return False
    if nplat >= 1:
        log.info("OpenCL auto-detect: %d platform(s) found → enabling OpenCL", nplat)
        return True
    log.info("OpenCL auto-detect: 0 platforms → disabling OpenCL")
    return False
