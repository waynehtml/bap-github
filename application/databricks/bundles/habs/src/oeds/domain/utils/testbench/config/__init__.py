"""Expose loading and variable resolution for Testbench case definitions."""

from .config_utils import load_test_case

# Case-file layout and rendering details remain private to config_utils.
__all__ = ["load_test_case"]
