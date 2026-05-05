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

**Symptom:** `RuntimeError: CmdStan not found.`

**Fix:** Install CmdStan for your setup:

```bash
# pip install
python -c "import cmdstanpy; cmdstanpy.install_cmdstan()"

# conda (recommended — sets CMDSTAN automatically)
conda install -c conda-forge cmdstan=2.36.0

# point to an existing install
export CMDSTAN=~/.cmdstan/cmdstan-2.36.0
```

TEXAS searches `CMDSTAN` env var → conda prefix → `~/.cmdstan/` → cmdstanpy default. Any version ≥ 2.23.0 is accepted.
