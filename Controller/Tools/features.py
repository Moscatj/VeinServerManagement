from __future__ import annotations

"""Feature flag helpers exposed for Controllers and Tools."""

from config_helper import is_feature_enabled as _is_feature_enabled

__all__ = ["is_feature_enabled"]


def is_feature_enabled(feature_key: str, default: bool = True) -> bool:
    """Wrapper that keeps the import path consistent for Tools modules."""
    return _is_feature_enabled(feature_key, default)
