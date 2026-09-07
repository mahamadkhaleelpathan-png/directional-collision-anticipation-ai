"""Shared utility functions for dashboard components."""


def risk_color(level: str) -> str:
    """Map risk level to hex color."""
    return {
        "SAFE": "#00cc00",
        "LOW": "#00cc00",
        "MEDIUM": "#ffaa00",
        "HIGH": "#ff6600",
        "CRITICAL": "#ff0000",
    }.get(level, "#888888")
