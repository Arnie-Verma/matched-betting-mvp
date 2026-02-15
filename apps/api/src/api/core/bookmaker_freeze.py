"""
Phase A bookmaker onboarding freeze controls.

This module provides a single source of truth for temporary freeze policy
enforcement while scraper hardening is in progress.
"""
from __future__ import annotations

import os
from typing import Iterable


BOOKMAKER_FREEZE_UNIBET_ENV = "BOOKMAKER_FREEZE_UNIBET"


def _env_flag_enabled(name: str, *, default: bool) -> bool:
    """Read a boolean-like env flag with a safe default."""
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() not in {"0", "false", "no", "off"}


def is_unibet_frozen() -> bool:
    """
    Return True when Unibet is frozen for onboarding/activation.

    Default is True so local/staging/prod stay frozen unless explicitly
    disabled after hardening GO.
    """
    return _env_flag_enabled(BOOKMAKER_FREEZE_UNIBET_ENV, default=True)


def is_bookmaker_frozen(bookmaker_code: str) -> bool:
    """Return whether a bookmaker is frozen by policy."""
    code = (bookmaker_code or "").strip().lower()
    return code == "unibet" and is_unibet_frozen()


def filter_frozen_bookmaker_codes(bookmaker_codes: Iterable[str]) -> list[str]:
    """Filter frozen bookmakers from a list of bookmaker codes."""
    return [code for code in bookmaker_codes if not is_bookmaker_frozen(code)]
