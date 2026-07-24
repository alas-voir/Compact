def crossfade_gains(progress: float) -> tuple[float, float]:
    """Return linear fade-out and fade-in gains for normalized progress."""
    fraction = max(0.0, min(1.0, float(progress)))
    return 1.0 - fraction, fraction
