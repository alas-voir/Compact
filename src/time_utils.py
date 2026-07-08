def format_duration_mmss(value: int | float | str | None) -> str:
    if value is None:
        return ""

    total_seconds: float | None = None

    if isinstance(value, (int, float)):
        total_seconds = float(value)
    elif isinstance(value, str):
        raw = value.strip()
        if not raw:
            return ""
        if ":" in raw:
            parts = raw.split(":")
            try:
                if len(parts) == 2:
                    minutes, seconds = parts
                    total_seconds = int(minutes) * 60 + float(seconds)
                elif len(parts) == 3:
                    hours, minutes, seconds = parts
                    total_seconds = (
                        int(hours) * 3600 + int(minutes) * 60 + float(seconds)
                    )
            except ValueError:
                return ""
        else:
            try:
                total_seconds = float(raw)
            except ValueError:
                return ""

    if total_seconds is None or total_seconds < 0:
        return ""

    rounded_seconds = int(round(total_seconds))
    minutes, seconds = divmod(rounded_seconds, 60)
    return f"{minutes:02d}:{seconds:02d}"
