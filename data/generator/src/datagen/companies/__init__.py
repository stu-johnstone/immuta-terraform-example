"""The companies, and every script generated for them."""

from __future__ import annotations

from ..model import Script
from . import harbourstone


def scripts() -> list[Script]:
    return [*harbourstone.scripts()]
