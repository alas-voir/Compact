import math
import re
from functools import lru_cache

from mutagen import File as MutagenFile


_GAIN_PATTERN = re.compile(r"[-+]?\d+(?:\.\d+)?")


def _gain_from_text(value: object) -> float | None:
    match = _GAIN_PATTERN.search(str(value))
    if match is None:
        return None
    try:
        return float(match.group(0))
    except ValueError:
        return None


@lru_cache(maxsize=2048)
def replaygain_volume_factor(file_path: str) -> float:
    """Return the ReplayGain/RVA2 linear volume factor for an audio file."""
    try:
        audio = MutagenFile(file_path)
        tags = getattr(audio, "tags", None)
        if tags is None:
            return 1.0

        gain_db: float | None = None
        for key in tags.keys():
            normalized_key = str(key).casefold()
            if "replaygain_track_gain" not in normalized_key:
                continue
            entry = tags[key]
            values = getattr(entry, "text", entry)
            if isinstance(values, (list, tuple)):
                values = values[0] if values else ""
            gain_db = _gain_from_text(values)
            if gain_db is not None:
                break

        if gain_db is None:
            for key in tags.keys():
                if not str(key).casefold().startswith("rva2"):
                    continue
                adjustment = getattr(tags[key], "gain", None)
                if adjustment is not None:
                    gain_db = float(adjustment)
                    break

        if gain_db is None:
            return 1.0
        return max(0.1, min(4.0, math.pow(10.0, gain_db / 20.0)))
    except Exception:
        return 1.0
