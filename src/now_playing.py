import sys

from PyQt6.QtCore import QObject, pyqtSignal


class MacOSNowPlaying(QObject):
    command_received = pyqtSignal(str)

    def __init__(self) -> None:
        super().__init__()
        self.available = False
        self.info: dict = {}
        self._artwork_handler = None
        self._command_handlers: list = []
        self._command_tokens: list[tuple[object, object]] = []
        if sys.platform != "darwin":
            return
        try:
            from MediaPlayer import MPNowPlayingInfoCenter, MPRemoteCommandCenter

            self.center = MPNowPlayingInfoCenter.defaultCenter()
            self.command_center = MPRemoteCommandCenter.sharedCommandCenter()
            self._register_remote_commands()
            self.available = True
        except Exception:
            self.available = False

    def _register_remote_commands(self) -> None:
        from MediaPlayer import MPRemoteCommandHandlerStatusSuccess

        commands = (
            (self.command_center.togglePlayPauseCommand(), "toggle"),
            (self.command_center.playCommand(), "play"),
            (self.command_center.pauseCommand(), "pause"),
            (self.command_center.nextTrackCommand(), "next"),
            (self.command_center.previousTrackCommand(), "previous"),
        )
        for command, command_name in commands:
            command.setEnabled_(True)

            def handler(_event, name=command_name):
                self.command_received.emit(name)
                return MPRemoteCommandHandlerStatusSuccess

            self._command_handlers.append(handler)
            token = command.addTargetWithHandler_(handler)
            self._command_tokens.append((command, token))

    def _set_playback_state(self, playing: bool, *, stopped: bool = False) -> None:
        if not self.available or not hasattr(self.center, "setPlaybackState_"):
            return
        try:
            from MediaPlayer import (
                MPNowPlayingPlaybackStatePaused,
                MPNowPlayingPlaybackStatePlaying,
                MPNowPlayingPlaybackStateStopped,
            )

            state = (
                MPNowPlayingPlaybackStateStopped
                if stopped
                else (
                    MPNowPlayingPlaybackStatePlaying
                    if playing
                    else MPNowPlayingPlaybackStatePaused
                )
            )
            self.center.setPlaybackState_(state)
        except Exception:
            return

    def set_track(
        self,
        *,
        title: str,
        artist: str,
        album: str,
        artwork_data: bytes | None,
        duration_seconds: float = 0.0,
        position_seconds: float = 0.0,
        playing: bool = False,
    ) -> None:
        if not self.available:
            return
        try:
            from MediaPlayer import (
                MPMediaItemArtwork,
                MPMediaItemPropertyAlbumTitle,
                MPMediaItemPropertyArtist,
                MPMediaItemPropertyArtwork,
                MPMediaItemPropertyPlaybackDuration,
                MPMediaItemPropertyTitle,
                MPNowPlayingInfoPropertyDefaultPlaybackRate,
                MPNowPlayingInfoPropertyElapsedPlaybackTime,
                MPNowPlayingInfoPropertyPlaybackRate,
            )

            self.info = {
                MPMediaItemPropertyTitle: title or "Без названия",
                MPMediaItemPropertyArtist: artist or "Неизвестный автор",
                MPNowPlayingInfoPropertyElapsedPlaybackTime: float(position_seconds),
                MPNowPlayingInfoPropertyPlaybackRate: 1.0 if playing else 0.0,
                MPNowPlayingInfoPropertyDefaultPlaybackRate: 1.0,
            }
            if album:
                self.info[MPMediaItemPropertyAlbumTitle] = album
            if duration_seconds > 0:
                self.info[MPMediaItemPropertyPlaybackDuration] = float(
                    duration_seconds
                )
            if artwork_data:
                from AppKit import NSImage
                from Foundation import NSData

                data = NSData.dataWithBytes_length_(artwork_data, len(artwork_data))
                image = NSImage.alloc().initWithData_(data)
                if image is not None:
                    self._artwork_handler = lambda _size, cover=image: cover
                    artwork = (
                        MPMediaItemArtwork.alloc().initWithBoundsSize_requestHandler_(
                            image.size(), self._artwork_handler
                        )
                    )
                    self.info[MPMediaItemPropertyArtwork] = artwork
            self.center.setNowPlayingInfo_(self.info)
            self._set_playback_state(playing)
        except Exception:
            return

    def update_playback(
        self,
        *,
        position_seconds: float,
        duration_seconds: float,
        playing: bool,
    ) -> None:
        if not self.available or not self.info:
            return
        try:
            from MediaPlayer import (
                MPMediaItemPropertyPlaybackDuration,
                MPNowPlayingInfoPropertyElapsedPlaybackTime,
                MPNowPlayingInfoPropertyPlaybackRate,
            )

            self.info[MPNowPlayingInfoPropertyElapsedPlaybackTime] = float(
                position_seconds
            )
            self.info[MPNowPlayingInfoPropertyPlaybackRate] = (
                1.0 if playing else 0.0
            )
            if duration_seconds > 0:
                self.info[MPMediaItemPropertyPlaybackDuration] = float(
                    duration_seconds
                )
            self.center.setNowPlayingInfo_(self.info)
            self._set_playback_state(playing)
        except Exception:
            return

    def clear(self) -> None:
        if not self.available:
            return
        try:
            self.info = {}
            self._artwork_handler = None
            self.center.setNowPlayingInfo_(None)
            self._set_playback_state(False, stopped=True)
        except Exception:
            return

    def shutdown(self) -> None:
        if not self.available:
            return
        self.clear()
        for command, token in self._command_tokens:
            try:
                command.removeTarget_(token)
            except Exception:
                pass
        self._command_tokens.clear()
        self._command_handlers.clear()
