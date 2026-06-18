"""
TEXAS/utils/system_info.py

System Configuration Summary for Performance Reporting
Usage: 
    from TEXAS.utils.system_info import print_system_summary, get_system_summary
    print_system_summary()
"""

import os
import platform
import psutil
import subprocess
import gc
import tracemalloc
import multiprocessing
from datetime import datetime
import json

def get_cpu_info():
    """Get detailed CPU information"""
    try:
        # Try to get CPU model from /proc/cpuinfo (Linux)
        cpu_model = None
        with open('/proc/cpuinfo', 'r') as f:
            for line in f:
                if 'model name' in line:
                    cpu_model = line.split(':')[1].strip()
                    break
        if cpu_model is None:
            cpu_model = platform.processor() or "Unknown"
    except:
        cpu_model = platform.processor() or "Unknown"
    
    return {
        "model": cpu_model,
        "physical_cores": psutil.cpu_count(logical=False),
        "logical_cores": psutil.cpu_count(logical=True),
        "max_frequency": f"{psutil.cpu_freq().max:.0f} MHz" if psutil.cpu_freq() else "Unknown"
    }


def get_memory_info():
    """Get memory information"""
    mem = psutil.virtual_memory()
    swap = psutil.swap_memory()
    
    return {
        "total_ram": f"{mem.total / (1024**3):.1f} GB",
        "available_ram": f"{mem.available / (1024**3):.1f} GB",
        "swap_total": f"{swap.total / (1024**3):.1f} GB",
        "swap_used": f"{swap.used / (1024**3):.1f} GB"
    }

def get_disk_info():
    """Get disk information for main drive"""
    try:
        disk = psutil.disk_usage('/')
        return {
            "total_space": f"{disk.total / (1024**3):.1f} GB",
            "free_space": f"{disk.free / (1024**3):.1f} GB",
            "used_space": f"{disk.used / (1024**3):.1f} GB"
        }
    except:
        return {"error": "Could not retrieve disk info"}

def get_python_env():
    """Get Python environment information"""
    return {
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "architecture": platform.architecture()[0]
    }

def get_container_info():
    """Check if running in container"""
    container_info = {
        "in_container": False,
        "container_type": None
    }
    
    try:
        # Check for container indicators
        with open('/proc/1/cgroup', 'r') as f:
            cgroup_content = f.read()
            if 'docker' in cgroup_content:
                container_info["in_container"] = True
                container_info["container_type"] = "Docker"
            elif 'lxc' in cgroup_content:
                container_info["in_container"] = True
                container_info["container_type"] = "LXC"
    except:
        pass
    
    # Check for dev container
    if 'CODESPACES' in subprocess.os.environ:
        container_info["in_container"] = True
        container_info["container_type"] = "GitHub Codespaces"
    elif 'REMOTE_CONTAINERS' in subprocess.os.environ:
        container_info["in_container"] = True
        container_info["container_type"] = "VS Code Dev Container"
    
    return container_info

def get_stan_info():
    """Get Stan/CmdStan information if available"""
    stan_info = {}
    
    try:
        import cmdstanpy
        stan_info["cmdstanpy_version"] = cmdstanpy.__version__
        try:
            stan_info["cmdstan_version"] = ".".join(map(str, cmdstanpy.cmdstan_version()))
            stan_info["cmdstan_path"] = cmdstanpy.cmdstan_path()
        except:
            stan_info["cmdstan_version"] = "Not installed"
            stan_info["cmdstan_path"] = "Not found"
    except ImportError:
        stan_info["cmdstanpy_version"] = "Not installed"
    
    return stan_info

def get_key_packages():
    """Get versions of key scientific packages"""
    packages = {}
    
    key_libs = ['numpy', 'pandas', 'xarray', 'scipy', 'matplotlib']
    
    for lib in key_libs:
        try:
            module = __import__(lib)
            packages[lib] = getattr(module, '__version__', 'Unknown version')
        except ImportError:
            packages[lib] = 'Not installed'
    
    return packages

def generate_system_summary():
    """Generate complete system summary"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    summary = {
        "timestamp": timestamp,
        "system": {
            "os": f"{platform.system()} {platform.release()}",
            "machine": platform.machine(),
            "hostname": platform.node()
        },
        "cpu": get_cpu_info(),
        "memory": get_memory_info(),
        "disk": get_disk_info(),
        "python": get_python_env(),
        "container": get_container_info(),
        "stan": get_stan_info(),
        "packages": get_key_packages()
    }
    
    return summary

def print_summary(summary):
    """Print formatted summary"""
    print("=" * 60)
    print("SYSTEM CONFIGURATION SUMMARY")
    print("=" * 60)
    print(f"Generated: {summary['timestamp']}")
    print()
    
    # System Info
    print("🖥️  SYSTEM:")
    print(f"   OS: {summary['system']['os']}")
    print(f"   Machine: {summary['system']['machine']}")
    print(f"   Hostname: {summary['system']['hostname']}")
    print()
    
    # CPU Info
    cpu = summary['cpu']
    print("🔧 CPU:")
    print(f"   Model: {cpu['model']}")
    print(f"   Cores: {cpu['physical_cores']} physical, {cpu['logical_cores']} logical")
    print(f"   Max Frequency: {cpu['max_frequency']}")
    print()
    
    # Memory Info
    mem = summary['memory']
    print("💾 MEMORY:")
    print(f"   RAM: {mem['total_ram']} total, {mem['available_ram']} available")
    print(f"   Swap: {mem['swap_total']} total, {mem['swap_used']} used")
    print()
    
    # Disk Info
    disk = summary['disk']
    print("💿 DISK:")
    if 'error' not in disk:
        print(f"   Total: {disk['total_space']}")
        print(f"   Free: {disk['free_space']}")
        print(f"   Used: {disk['used_space']}")
    else:
        print(f"   {disk['error']}")
    print()
    
    # Container Info
    container = summary['container']
    print("📦 CONTAINER:")
    if container['in_container']:
        print(f"   Running in: {container['container_type']}")
    else:
        print("   Native environment (not containerized)")
    print()
    
    # Python Info
    python = summary['python']
    print("🐍 PYTHON:")
    print(f"   Version: {python['python_version']}")
    print(f"   Implementation: {python['python_implementation']}")
    print(f"   Architecture: {python['architecture']}")
    print()
    
    # Stan Info
    stan = summary['stan']
    print("📊 STAN:")
    print(f"   CmdStanPy: {stan.get('cmdstanpy_version', 'Not available')}")
    print(f"   CmdStan: {stan.get('cmdstan_version', 'Not available')}")
    if 'cmdstan_path' in stan:
        print(f"   Path: {stan['cmdstan_path']}")
    print()
    
    # Package Versions
    packages = summary['packages']
    print("📚 KEY PACKAGES:")
    for pkg, version in packages.items():
        print(f"   {pkg}: {version}")
    print()
    
    print("=" * 60)

def get_system_summary():
    """Generate complete system summary - main API function"""
    return generate_system_summary()

def print_system_summary():
    """Print formatted system summary - main API function"""
    summary = generate_system_summary()
    print_summary(summary)
    return summary

def save_system_summary(filepath=None):
    """Save system summary to JSON file"""
    from datetime import datetime

    summary = generate_system_summary()

    if filepath is None:
        filepath = f"system_config_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    with open(filepath, 'w') as f:
        json.dump(summary, f, indent=2)

    print(f"✅ System configuration saved to: {filepath}")
    return filepath


def suggest_stan_sampling_kwargs() -> dict:
    """
    Return optimized Stan sampling kwargs for the current machine.

    Strategy:
    - ``chains``: always 4 (standard for convergence diagnostics).
    - ``parallel_chains``: min(4, logical_available) — run chains concurrently,
      respects cgroup/Docker CPU limits on Linux.
    - ``threads_per_chain``: physical_cores // 4, only when physical_cores > 4.
      Exploits ``reduce_sum`` within each chain (STAN_THREADS compilation is
      handled automatically by ``get_invT_posterior``).  Physical cores are used
      (not logical/hyperthreaded) because Stan HMC is FP-bound and hyperthreads
      give negligible throughput gain while doubling apparent CPU usage.

    Returns a dict containing only the keys that differ from CmdStanPy defaults,
    so callers can safely merge it with their own kwargs.
    """
    try:
        # Respects cgroup/Docker --cpus limits on Linux
        logical_available = len(os.sched_getaffinity(0))
    except AttributeError:
        logical_available = psutil.cpu_count(logical=True) or 1

    # Physical cores for threading: HMC is FP-bound, hyperthreads don't help
    physical_cores = psutil.cpu_count(logical=False) or 1

    chains = 4
    parallel_chains = min(chains, logical_available)
    threads_per_chain = physical_cores // chains  # 0 when physical_cores < 4

    result: dict = {
        "chains": chains,
        "parallel_chains": parallel_chains,
    }
    if threads_per_chain > 1:
        result["threads_per_chain"] = threads_per_chain

    return result


def simple_memory_check():
    """Simple memory tracking using tracemalloc (must be started before calling)."""
    gc.collect()
    if tracemalloc.is_tracing():
        current, peak = tracemalloc.get_traced_memory()
        return {
            'current_mb': current / 1024 / 1024,
            'peak_mb': peak / 1024 / 1024,
        }
    return {'current_mb': 0, 'peak_mb': 0}


def get_system_info():
    """Collect system information dict for embedding in posterior metadata."""
    try:
        cpu_freq = psutil.cpu_freq()
        cpu_freq_current = cpu_freq.current if cpu_freq else None
        cpu_freq_max = cpu_freq.max if cpu_freq else None
    except (AttributeError, OSError):
        cpu_freq_current = None
        cpu_freq_max = None

    try:
        memory = psutil.virtual_memory()
        total_memory_gb = memory.total / (1024 ** 3)
        available_memory_gb = memory.available / (1024 ** 3)
    except Exception:
        total_memory_gb = None
        available_memory_gb = None

    return {
        'system': platform.system(),
        'platform': platform.platform(),
        'architecture': platform.architecture()[0],
        'processor': platform.processor(),
        'hostname': platform.node(),
        'cpu_count_logical': multiprocessing.cpu_count(),
        'cpu_count_physical': psutil.cpu_count(logical=False) if hasattr(psutil, 'cpu_count') else None,
        'cpu_freq_current_mhz': round(cpu_freq_current) if cpu_freq_current else None,
        'cpu_freq_max_mhz': round(cpu_freq_max) if cpu_freq_max else None,
        'total_memory_gb': round(total_memory_gb, 1) if total_memory_gb else None,
        'available_memory_gb': round(available_memory_gb, 1) if available_memory_gb else None,
        'python_version': platform.python_version(),
        'python_implementation': platform.python_implementation(),
        'run_timestamp': datetime.now().isoformat(),
    }