"""
Utility functions for plugin requirement checking.
"""

import os
import shutil
import importlib.util
from typing import Tuple, List


def check_binary_available(bin_name: str) -> bool:
    """
    Check if a binary is available in PATH.

    Args:
        bin_name: Name of the binary to check

    Returns:
        True if binary is available, False otherwise
    """
    return shutil.which(bin_name) is not None


def check_env_var(var_name: str) -> bool:
    """
    Check if an environment variable is set.

    Args:
        var_name: Name of the environment variable

    Returns:
        True if variable is set and non-empty, False otherwise
    """
    value = os.environ.get(var_name)
    return value is not None and value != ""


def check_python_package(package_name: str) -> bool:
    """
    Check if a Python package is installed and importable.

    Args:
        package_name: Name of the Python package

    Returns:
        True if package is available, False otherwise
    """
    try:
        spec = importlib.util.find_spec(package_name)
        return spec is not None
    except (ImportError, ModuleNotFoundError, ValueError):
        return False


def check_all_requirements(requires: "Requirement") -> Tuple[bool, List[str]]:
    """
    Check all requirements for a plugin.

    Args:
        requires: Requirement object with bins, python_packages, env_vars

    Returns:
        Tuple of (all_met, missing_requirements)
    """
    from .manifest import Requirement

    missing = []

    # Check binaries
    for bin_name in requires.bins:
        if not check_binary_available(bin_name):
            missing.append(f"binary: {bin_name}")

    # Check Python packages
    for package in requires.python_packages:
        if not check_python_package(package):
            missing.append(f"python package: {package}")

    # Check environment variables
    for var in requires.env_vars:
        if not check_env_var(var):
            missing.append(f"environment variable: {var}")

    return len(missing) == 0, missing
