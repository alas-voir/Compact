from urllib.parse import parse_qs, urlencode, urlparse, urlunparse


def normalize_youtube_track_url(url: str) -> str:
    source = (url or "").strip()
    if not source:
        return source

    parsed = urlparse(source)
    host = parsed.netloc.lower()
    if host.startswith("www."):
        host = host[4:]

    if host not in {"youtube.com", "m.youtube.com", "music.youtube.com", "youtu.be"}:
        return source

    query = parse_qs(parsed.query)

    if host == "youtu.be":
        video_id = parsed.path.strip("/").split("/", 1)[0]
        if not video_id:
            return source
        clean_query: dict[str, list[str]] = {"v": [video_id]}
        for key in ("t", "start", "end"):
            values = query.get(key)
            if values:
                clean_query[key] = values[:1]
        return urlunparse(
            (
                "https",
                "www.youtube.com",
                "/watch",
                "",
                urlencode(clean_query, doseq=True),
                "",
            )
        )

    if parsed.path == "/watch":
        video_id = (query.get("v") or [""])[0].strip()
        if not video_id:
            return source
        clean_query: dict[str, list[str]] = {"v": [video_id]}
        for key in ("t", "start", "end"):
            values = query.get(key)
            if values:
                clean_query[key] = values[:1]
        return urlunparse(
            (
                "https",
                "www.youtube.com",
                "/watch",
                "",
                urlencode(clean_query, doseq=True),
                "",
            )
        )

    if parsed.path.startswith("/shorts/"):
        short_id = parsed.path.split("/shorts/", 1)[1].split("/", 1)[0].strip()
        if not short_id:
            return source
        return urlunparse(
            (
                "https",
                "www.youtube.com",
                "/watch",
                "",
                urlencode({"v": short_id}),
                "",
            )
        )

    return source
