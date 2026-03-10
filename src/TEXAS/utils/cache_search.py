# DEPRECATED: Not used by any active code path. Kept for reference only.
# src/TEXAS/utils/cache_search.py
"""
Cache file search and filtering utilities for TEXAS package.

Provides grep-like functionality for searching through forward and invT cache files.
"""

from typing import Literal, List, Optional
from pathlib import Path
import re
import fnmatch
from .paths import INVT_CACHE_DIR, POSTERIOR_CACHE_DIR

def grep_cache_files(pattern: str, model_type: Literal["forward", "invT"] = "invT", case_sensitive: bool = False):
    """Grep-like search through cache filenames"""
    cache_dir = POSTERIOR_CACHE_DIR if model_type == "forward" else INVT_CACHE_DIR
    files = list(cache_dir.glob('*.nc'))
    
    if case_sensitive:
        regex = re.compile(pattern)
    else:
        regex = re.compile(pattern, re.IGNORECASE)
    
    matches = [f for f in files if regex.search(f.name)]
    
    print(f"Found {len(matches)} {model_type} files matching '{pattern}':")
    for i, file in enumerate(sorted(matches), 1):
        print(f"{i:2d}. {file.name}")
    
    return matches

def filter_cache_files(model_type: Literal["forward", "invT"] = "invT", **conditions):
    """Filter cache files by multiple conditions"""
    cache_dir = POSTERIOR_CACHE_DIR if model_type == "forward" else INVT_CACHE_DIR
    files = list(cache_dir.glob('*.nc'))
    
    filtered = files
    for key, value in conditions.items():
        if key == "contains":
            if isinstance(value, str):
                value = [value]
            for pattern in value:
                filtered = [f for f in filtered if pattern in f.name]
        
        elif key == "not_contains":
            if isinstance(value, str):
                value = [value]
            for pattern in value:
                filtered = [f for f in filtered if pattern not in f.name]
        
        elif key == "starts_with":
            filtered = [f for f in filtered if f.name.startswith(value)]
        
        elif key == "ends_with":
            filtered = [f for f in filtered if f.name.endswith(value)]
    
    print(f"Found {len(filtered)} {model_type} files:")
    for i, file in enumerate(sorted(filtered), 1):
        print(f"{i:2d}. {file.name}")
    
    return filtered

def search_cache(search_terms, model_type: Literal["forward", "invT"] = "invT", mode: str = "all"):
    """
    Search cache files with multiple terms
    mode: 'all' (AND), 'any' (OR), 'none' (NOT)
    """
    cache_dir = POSTERIOR_CACHE_DIR if model_type == "forward" else INVT_CACHE_DIR
    files = list(cache_dir.glob('*.nc'))
    
    if isinstance(search_terms, str):
        search_terms = [search_terms]
    
    results = []
    for file in files:
        filename = file.name.lower()  # Case insensitive
        
        if mode == "all":
            if all(term.lower() in filename for term in search_terms):
                results.append(file)
        elif mode == "any":
            if any(term.lower() in filename for term in search_terms):
                results.append(file)
        elif mode == "none":
            if not any(term.lower() in filename for term in search_terms):
                results.append(file)
    
    print(f"Search: {search_terms} (mode: {mode}) in {model_type} cache")
    print(f"Found {len(results)} files:")
    for i, file in enumerate(sorted(results), 1):
        print(f"{i:2d}. {file.name}")
    
    return results

def wildcard_search(pattern: str, model_type: Literal["forward", "invT"] = "invT"):
    """Unix-style wildcard matching"""
    cache_dir = POSTERIOR_CACHE_DIR if model_type == "forward" else INVT_CACHE_DIR
    files = list(cache_dir.glob('*.nc'))
    matches = [f for f in files if fnmatch.fnmatch(f.name, pattern)]
    
    print(f"Pattern: {pattern} in {model_type} cache")
    print(f"Found {len(matches)} matches:")
    for i, file in enumerate(sorted(matches), 1):
        print(f"{i:2d}. {file.name}")
    
    return matches

def list_cache_files(model_type: Literal["forward", "invT"] = "invT", limit: int = 20):
    """List all files in cache directory"""
    cache_dir = POSTERIOR_CACHE_DIR if model_type == "forward" else INVT_CACHE_DIR
    files = list(cache_dir.glob('*.nc'))
    
    print(f"{model_type.title()} cache files ({len(files)} total):")
    for i, file in enumerate(sorted(files), 1):
        print(f"{i:2d}. {file.name}")
        if i >= limit:
            remaining = len(files) - limit
            if remaining > 0:
                print(f"    ... and {remaining} more files")
            break
    
    return files