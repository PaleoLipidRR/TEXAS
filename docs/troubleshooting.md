# Troubleshooting

## Permission errors after running Docker

**Symptom:** After using the Docker container (or VS Code Dev Container), you get `Permission denied` errors on the host when trying to edit files, run `git`, or build the package — even though you own the repository.

**Cause:** The container runs as an internal user (`micromamba`, UID 57440). When it writes files into the bind-mounted repo directory, those files are owned by UID 57440 on the host. Your host user (e.g. UID 1000) can no longer write them.

**Permanent fix (Dev Container users):** `devcontainer.json` sets `"updateRemoteUserUID": true`, which tells VS Code to remap the container user's UID to match yours at startup. After rebuilding the container once, files Docker creates will be owned by your host user.

**If you still hit it (e.g. after `docker compose up` tests):** restore ownership from the repo root:

```bash
sudo chown -R $USER:$USER .
```

For convenience, add a shell alias:

```bash
echo "alias fix-texas='sudo chown -R \$USER:\$USER /path/to/TEXAS'" >> ~/.bashrc && source ~/.bashrc
```

---

## Stan compilation fails with `Permission denied` on `.hpp` file

**Symptom:**
```
Internal compiler error:
(Sys_error ".../stan_models/model_name.hpp: Permission denied")
```

**Cause:** Stan's compiler (`stanc`) writes an intermediate `.hpp` file into the same directory as the `.stan` source. If that directory is owned by a different user (from a prior Docker run), the current user cannot write it.

**Fix:** TEXAS (v0.2.0+) compiles all Stan models into `~/.texas/stan_cache/` — a directory always writable by the current user. Upgrade if needed:

```bash
pip install --upgrade texas-psm
```

Override the build directory:

```bash
export TEXAS_STAN_BUILD_DIR=/tmp/texas_stan
```

---

## Stan binary incompatible after switching between Docker and local env

**Symptom:**
```
Stan model 'model_name' was compiled for a different environment (exit code 127).
The old binary has been removed and the model will be recompiled...
```

**This is expected and self-healing.** Stan binaries compiled inside Docker (Linux x86_64 ELF) cannot run on macOS, and vice versa. TEXAS detects this automatically, deletes the stale binary, and recompiles for the current environment. No action needed — sampling will proceed after a one-time recompilation.

---

## CmdStan not found

**Symptom:** `RuntimeError: No working CmdStan installation found`, or at import a
`UserWarning: CmdStan not found — Stan sampling ... will not be available`.

**First, diagnose.** `texas-doctor` reports cmdstanpy, the CmdStan path/version, the C++
compiler, and — crucially — *why* discovery failed. It runs on every shell (PowerShell,
CMD, bash, zsh):

```bash
texas-doctor            # or:  python -c "import TEXAS; TEXAS.doctor()"
```

**Fix — one call (pip / uv):** installs the tested version, points TEXAS at it, and
verifies:

```python
import TEXAS
TEXAS.install_cmdstan()        # shell equivalent: texas-install-cmdstan
```

**Fix — manual install** (if you prefer to manage the version yourself):

```bash
# pip / uv  (installs to ~/.cmdstan/cmdstan-<version>)
python -c "import cmdstanpy; cmdstanpy.install_cmdstan(version='2.36.0')"

# conda / conda-forge (pre-built; sets CMDSTAN automatically on activation)
conda install -c conda-forge cmdstan=2.36.0
```

**Fix — point TEXAS at an existing install.** Set `CMDSTAN` *before* importing TEXAS:

=== "PowerShell (Windows)"

    ```powershell
    $env:CMDSTAN = "$HOME\.cmdstan\cmdstan-2.36.0"   # this session
    setx CMDSTAN "$HOME\.cmdstan\cmdstan-2.36.0"      # persist (reopen terminal)
    ```

=== "bash / zsh (Linux, macOS, WSL2)"

    ```bash
    export CMDSTAN=~/.cmdstan/cmdstan-2.36.0          # add to ~/.bashrc to persist
    ```

TEXAS searches, in order: `CMDSTAN` env var → `$CONDA_PREFIX/bin/cmdstan` →
`<python prefix>/bin/cmdstan` → the highest `cmdstan-*` under `/opt/cmdstan/`, `~/.cmdstan/`,
`/usr/local/cmdstan/` → cmdstanpy's configured default. Any version ≥ 2.23.0 is accepted.
See [Installation → CmdStan](installation.md#cmdstan-install-discovery-and-verification).

---

## CmdStan directory exists but the compiler binaries are missing or unusable

**Symptom:** `UserWarning: CMDSTAN env var points to '…/cmdstan-2.36.0' but no stanc binary
was found there. Ignoring and searching standard paths.` — followed by *CmdStan not found*.
`texas-doctor` reports it explicitly:

```
X   CmdStan           not found
    ! CMDSTAN env var -> '…/cmdstan-2.36.0' exists but 'bin/stanc' is missing:
      the CmdStan C++ toolchain was never built there.
```

**Cause:** `CMDSTAN` points at a directory that is not a *built* CmdStan. The most common
reasons:

- The download was interrupted, or only the sources were unpacked — `bin/stanc`
  (`bin\stanc.exe` on Windows) was never compiled.
- The path is stale (points at a version that was deleted or moved).
- Permissions: `bin/stanc` exists but is not executable (partial copy, restrictive ACLs, or
  a binary copied from another machine).

**Fix — one call:** `TEXAS.install_cmdstan()` detects exactly this half-built state and
reinstalls over it automatically (it sets `overwrite=True` for you):

```python
import TEXAS
TEXAS.install_cmdstan()        # shell equivalent: texas-install-cmdstan
```

**Fix — manual:** rebuild the toolchain in place, or reinstall cleanly:

```bash
# rebuild bin/stanc + supporting binaries for the CmdStan at $CMDSTAN
python -c "import cmdstanpy; cmdstanpy.rebuild_cmdstan()"

# or reinstall the whole thing (note the overwrite flag — required for a partial dir)
python -c "import cmdstanpy; cmdstanpy.install_cmdstan(version='2.36.0', overwrite=True)"
```

Then re-run `texas-doctor` — it should print `Stan sampling: READY`.

> A directory named `cmdstan-2.36.0` is **not** proof of a working install. TEXAS only
> accepts a path whose `bin/stanc` both exists and is executable; anything else is skipped
> with a warning so a broken `CMDSTAN` never silently shadows a good install further down
> the search order.

---

## Stan compilation fails with "compiler not found" / `make` errors

**Symptom:** CmdStan is found, but the first model compile fails with a missing `g++`,
`clang++`, `cl`, or `make`.

**Cause:** Every Stan model compiles to a native binary, so a C++ toolchain must be on
`PATH`. `texas-doctor` flags this as `✗ C++ compiler`.

**Fix:**

- **Linux:** `sudo apt install build-essential`
- **macOS:** `xcode-select --install`
- **Windows:** `python -m cmdstanpy.install_cxx_toolchain` (installs the RTools
  MinGW toolchain), or use the conda-forge `cmdstan` package, which ships a pre-built
  compiler.
