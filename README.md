# Compact

Compact is a desktop music player and local library manager built with PyQt6.
It combines music downloads and imports, library browsing, playback queue
management, and MP3 metadata editing in a compact three-panel interface.

Current version: **0.8.2**

## Features

### Music library

- Local library views for artists, albums, and playlists.
- A home page with quick access to recent and grouped library content.
- Track, artist, album, and playlist search.
- Dedicated artist, album, and playlist pages.
- Manual playlists with single-track and multi-track additions.
- Track-number sorting for albums and playlists.
- Context actions such as **Play next**.
- MP3 downloads through `yt-dlp` and bulk link imports from TXT files.
- MP3 artwork and metadata reading and editing.
- Automatic cleanup of artist folders that no longer contain any tracks.

### Playback

- Play and pause from track, album, and playlist cards.
- Previous and next track navigation.
- Seeking from track cards and the main progress bar.
- Editable playback queue with play, remove, and **Play next** actions.
- Playback history, including repeated entries.
- Shuffle playback without repetitions inside the active queue.
- Repeat queue and repeat-one modes.
- Automatic transition to the next available track.
- Configurable cross-fade.
- Optional ReplayGain-based volume normalization.
- Playback session persistence between application launches.
- Immediate removal of deleted tracks from playback, the queue, history, and
  visible library pages.

### Audio controls

- Volume slider with pointer and mouse-wheel control.
- Mute toggle that restores the previous volume.
- Dynamic volume-level icons.
- Audio output device selection.
- macOS Now Playing integration and media-key support.

### Interface

- Playback, metadata, and history modes in the right-hand panel.
- Current track, artist, album, artwork, and queue information.
- Animated disc-style artwork.
- Editing for track title, artist, album, track number, and cover art.
- Responsive panels and cards.
- Optional window transparency and blur.
- Configurable transparency for individual interface elements.
- Custom interface font selection.
- Light, dark, Tokyo Night, Nordic, Dracula, and Synthwave themes.
- Custom themes in JSON format.
- English and Russian interfaces.
- Custom language packs.
- Built-in GitHub Releases update checking and installation.
- Native macOS title bars, window controls, and standard close/quit behavior.

## Before downloading from YouTube

YouTube may require cookies from an authenticated browser session for downloads
to work correctly.

Before using `yt-dlp`:

1. Sign in to YouTube in your preferred browser.
2. Open **Compact → Settings**.
3. Under **YouTube cookies**, select the browser that contains the active
   YouTube session.
4. Close Settings and start the download.

Supported browser options:

- Safari
- Google Chrome
- Firefox
- Microsoft Edge
- Brave
- Chromium
- Zen
- Twilight

You can also select a cookies file manually. Browser or cookies-file access is
performed locally by `yt-dlp`; Compact does not upload browser cookies.

> [!IMPORTANT]
> Select the correct browser before starting a download. If no browser is
> selected, or the selected browser has no active YouTube session, `yt-dlp` may
> fail with an authentication, bot-check, or unavailable-format error.

## Keyboard shortcuts

| Action | macOS | Windows | Linux |
| --- | --- | --- | --- |
| Play or pause | `Space` | `Space` | `Space` |
| Increase volume | `Cmd + ↑` | `Ctrl + ↑` | `Ctrl + ↑` |
| Decrease volume | `Cmd + ↓` | `Ctrl + ↓` | `Ctrl + ↓` |
| Next track | `Cmd + →` | `Ctrl + →` | `Ctrl + →` |
| Previous track | `Cmd + ←` | `Ctrl + ←` | `Ctrl + ←` |
| Open Settings | `Cmd + ,` | `Ctrl + ,` | `Ctrl + ,` |
| Close the active window or dialog | `Cmd + W` | `Ctrl + W` | `Ctrl + W` |
| Quit Compact | `Cmd + Q` | `Ctrl + Q` | `Ctrl + Q` |
| Play, pause, next, or previous | System media keys | System media keys | System media keys |

`Space` does not toggle playback while a text field is focused. Availability of
system media keys depends on the operating system and desktop environment.

## Data storage

By default, Compact creates its library root at:

```text
~/Music/Compact
```

The library contains:

```text
Compact/
├── music/
└── playlists/
```

A different library root can be selected from the application.

On macOS, user resources and logs are stored in:

```text
~/Library/Application Support/Compact/
├── languages/
├── logs/
└── themes/
```

The main application log is:

```text
~/Library/Application Support/Compact/logs/compact.log
```

See [`assets/languages/README.md`](assets/languages/README.md) and
[`assets/themes/README.md`](assets/themes/README.md) for the custom language and
theme formats.

## Requirements

- Python 3.10 or newer.
- FFmpeg and FFprobe when running from source.
- A supported desktop environment for PyQt6.
- macOS for Now Playing integration and the prebuilt `.app`/`.dmg` package.

FFmpeg and FFprobe are bundled with the published macOS application, so no
separate installation or path configuration is required for that build.

All Python dependencies are listed in
[`requirements.txt`](requirements.txt).

## Run from source

### macOS and Linux

```bash
python3 -m venv .vnv
source .vnv/bin/activate
python3 -m pip install -r requirements.txt
python3 app.py
```

On macOS, the launcher script can also be used:

```bash
./start.command
```

### Windows

```powershell
py -m venv .vnv
.\.vnv\Scripts\Activate.ps1
py -m pip install -r requirements.txt
py app.py
```

When running from source, make sure both `ffmpeg` and `ffprobe` are available in
`PATH`, placed in the repository's `bin` directory, or selected from Compact's
FFmpeg setup dialog.

## Build for macOS

```bash
./build_macos.command
```

The script installs the required build dependencies, runs PyInstaller with
`Compact.spec`, and creates:

```text
dist/Compact.app
dist/Compact.dmg
```

Published builds are available on the
[GitHub Releases page](https://github.com/ZERv3/Compact/releases).

## Key technologies and libraries

| Technology | Used for |
| --- | --- |
| [Python](https://www.python.org/) | Application logic, library management, downloads, and background workers. |
| [PyQt6](https://www.riverbankcomputing.com/software/pyqt/) | Desktop interface, widgets, dialogs, threading signals, audio playback, output-device selection, and SVG rendering. |
| [yt-dlp](https://github.com/yt-dlp/yt-dlp) | YouTube metadata extraction, authenticated browser-cookie access, audio downloads, playlists, and download progress. |
| [FFmpeg and FFprobe](https://ffmpeg.org/) | Audio extraction and conversion, MP3 encoding, slicing, stream inspection, cover embedding, and metadata remuxing. |
| [Mutagen](https://mutagen.readthedocs.io/) | Reading and writing MP3/ID3 metadata, artwork, track numbers, duration, and ReplayGain values. |
| [PyObjC](https://pyobjc.readthedocs.io/) | Native macOS window behavior and MediaPlayer/Now Playing integration. |
| [certifi](https://github.com/certifi/python-certifi) | Bundled certificate authority store for reliable HTTPS requests in packaged builds. |
| [PyInstaller](https://pyinstaller.org/) | Packaging Python, PyQt6, certificates, assets, FFmpeg, and FFprobe into the macOS application bundle. |

The bundled macOS arm64 FFmpeg binaries are based on the static builds from
[`eugeneware/ffmpeg-static`](https://github.com/eugeneware/ffmpeg-static).

## License and third-party components

Compact depends on third-party open-source projects. Their respective licenses
continue to apply. Review the linked project pages and bundled component
licenses when redistributing the application.
