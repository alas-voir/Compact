import html
import re
import urllib.request

import spotipy
from spotipy.oauth2 import SpotifyClientCredentials

from .models import PlaylistEntry, SpotifyTrack


class SpotifyReaderError(RuntimeError):
    pass


class SpotifyPlaylistReader:
    def __init__(self, client_id: str, client_secret: str) -> None:
        if not client_id or not client_secret:
            raise SpotifyReaderError(
                "Не удалось инициализировать Spotify API. Укажите Spotify Client ID и Client Secret."
            )
        try:
            auth_manager = SpotifyClientCredentials(
                client_id=client_id,
                client_secret=client_secret,
            )
            self.client = spotipy.Spotify(auth_manager=auth_manager, requests_timeout=10, retries=2)
        except Exception as exc:
            raise SpotifyReaderError(
                "Не удалось инициализировать Spotify API. Проверьте Client ID и Client Secret."
            ) from exc

    def read_playlist(self, playlist_url: str) -> PlaylistEntry:
        playlist_id = self._extract_playlist_id(playlist_url)
        if not playlist_id:
            raise SpotifyReaderError("Не удалось извлечь ID Spotify-плейлиста из ссылки.")

        try:
            playlist = self.client.playlist(
                playlist_id,
                market="US",
            )
        except Exception as exc:
            raise SpotifyReaderError(f"Не удалось загрузить Spotify-плейлист: {exc}") from exc

        tracks_payload = playlist.get("tracks") or {}
        tracks: list[SpotifyTrack] = []
        tracks.extend(self._parse_tracks(tracks_payload))
        if not tracks:
            tracks.extend(self._parse_tracks(playlist))

        while tracks_payload.get("next"):
            try:
                tracks_payload = self.client.next(tracks_payload)
            except Exception as exc:
                raise SpotifyReaderError(f"Не удалось догрузить все треки плейлиста: {exc}") from exc
            tracks.extend(self._parse_tracks(tracks_payload))

        note = ""
        if not tracks:
            scraped_track_ids = self._scrape_playlist_track_ids(playlist_id)
            tracks.extend(self._load_tracks_by_ids(scraped_track_ids))
            if not tracks:
                note = (
                    "Spotify API вернул только метаданные плейлиста, а публичная страница "
                    "не дала доступных track-ссылок для fallback-импорта."
                )

        return PlaylistEntry(
            name=(playlist.get("name") or "Spotify Playlist").strip(),
            source="spotify",
            source_url=playlist_url.strip(),
            tracks=tracks,
            note=note,
        )

    def _parse_tracks(self, payload: dict) -> list[SpotifyTrack]:
        items = payload.get("items") or []
        result: list[SpotifyTrack] = []
        for item in items:
            track = item.get("track") or item.get("item") or item
            if track.get("type") != "track":
                continue
            title = (track.get("name") or "Без названия").strip()
            artists = ", ".join(
                artist.get("name", "").strip() for artist in (track.get("artists") or []) if artist.get("name")
            ) or "Неизвестный автор"
            album_payload = track.get("album") or {}
            album = (album_payload.get("name") or "").strip()
            spotify_url = (
                (track.get("external_urls") or {}).get("spotify")
                or track.get("uri")
                or ""
            ).strip()
            thumbnail_data = self._load_thumbnail(album_payload)
            result.append(
                SpotifyTrack(
                    title=title,
                    artists=artists,
                    album=album,
                    spotify_url=spotify_url,
                    thumbnail_data=thumbnail_data,
                )
            )
        return result

    def _load_thumbnail(self, album_payload: dict) -> bytes | None:
        images = album_payload.get("images") or []
        if not images:
            return None
        image_url = (images[0] or {}).get("url")
        if not image_url:
            return None
        try:
            with urllib.request.urlopen(image_url, timeout=15) as response:
                return response.read()
        except Exception:
            return None

    def _extract_playlist_id(self, playlist_url: str) -> str:
        match = re.search(r"playlist/([A-Za-z0-9]+)", playlist_url)
        if match:
            return match.group(1)
        if re.fullmatch(r"[A-Za-z0-9]+", playlist_url.strip()):
            return playlist_url.strip()
        return ""

    def _scrape_playlist_track_ids(self, playlist_id: str) -> list[str]:
        urls = [
            f"https://open.spotify.com/embed/playlist/{playlist_id}",
            f"https://open.spotify.com/playlist/{playlist_id}",
        ]
        patterns = [
            r"/track/([A-Za-z0-9]{22})",
            r"spotify:track:([A-Za-z0-9]{22})",
        ]

        for url in urls:
            try:
                request = urllib.request.Request(
                    url,
                    headers={
                        "User-Agent": (
                            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                            "AppleWebKit/537.36 (KHTML, like Gecko) "
                            "Chrome/124.0 Safari/537.36"
                        )
                    },
                )
                with urllib.request.urlopen(request, timeout=20) as response:
                    payload = response.read().decode("utf-8", errors="ignore")
            except Exception:
                continue

            found_ids: list[str] = []
            for pattern in patterns:
                found_ids.extend(re.findall(pattern, payload))
            deduped_ids = list(dict.fromkeys(found_ids))
            if deduped_ids:
                return deduped_ids
        return []

    def _load_tracks_by_ids(self, track_ids: list[str]) -> list[SpotifyTrack]:
        result: list[SpotifyTrack] = []
        for track_id in track_ids:
            try:
                track = self.client.track(track_id)
            except Exception:
                continue

            title = html.unescape((track.get("name") or "Без названия").strip())
            artists = ", ".join(
                html.unescape(artist.get("name", "").strip())
                for artist in (track.get("artists") or [])
                if artist.get("name")
            ) or "Неизвестный автор"
            album_payload = track.get("album") or {}
            album = html.unescape((album_payload.get("name") or "").strip())
            spotify_url = (
                (track.get("external_urls") or {}).get("spotify")
                or f"https://open.spotify.com/track/{track_id}"
            ).strip()
            thumbnail_data = self._load_thumbnail(album_payload)
            result.append(
                SpotifyTrack(
                    title=title,
                    artists=artists,
                    album=album,
                    spotify_url=spotify_url,
                    thumbnail_data=thumbnail_data,
                )
            )
        return result
