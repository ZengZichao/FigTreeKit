"""Tests for the CLI exit-code enumeration (``figtreekit._cli.ExitCode``).

Coverage:
- numeric values of the exit codes
- ``ExitCode`` is an ``int`` subclass
- each code is directly usable as a ``sys.exit`` argument
"""

import sys

import pytest

from figtreekit._cli import ExitCode


def test_exit_code_values_preserved() -> None:
    """The numeric values are a public contract and must not change."""
    assert int(ExitCode.SUCCESS) == 0
    assert int(ExitCode.GENERAL_ERROR) == 1
    assert int(ExitCode.USAGE_ERROR) == 2
    assert int(ExitCode.DATA_ERROR) == 3
    assert int(ExitCode.INTERRUPTED) == 130


def test_exit_code_is_int_subclass() -> None:
    """ExitCode must be an int subclass so it can be passed to sys.exit."""
    assert issubclass(ExitCode, int)
    # IntEnum members behave like ints (needed by sys.exit).
    assert isinstance(ExitCode.SUCCESS, int)


def test_exit_codes_are_sys_exit_compatible() -> None:
    """Each code must be directly usable as a sys.exit argument (no .value)."""
    for code in ExitCode:
        # Raises SystemExit with the code as the payload.
        with pytest.raises(SystemExit) as exc_info:
            sys.exit(code)
        assert exc_info.value.code == int(code)
