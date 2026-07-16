# Compact

PyQt6-приложение для импорта музыкальных источников, просмотра плейлистов и загрузки аудио в `mp3`.

## Что умеет

- импортировать YouTube-ссылки из `.txt`
- загружать `mp3` через `yt-dlp`
- работать с локальной библиотекой `music`
- хранить плейлисты в `playlists`
- редактировать метаданные и обложки `mp3`

## Структура данных

Приложение использует корневую папку `Compact`, внутри которой ожидаются:

- `music/`
- `playlists/`

Путь к этой папке можно выбрать в интерфейсе.

## Запуск

```bash
python3 -m venv .vnv
source .vnv/bin/activate
pip install -r requirements.txt
python3 app.py
```

Или:

```bash
./start.command
```

## Сборка macOS

```bash
./build_macos.command
```

Скрипт собирает:

- `dist/Compact.app`
- `dist/Compact.dmg`

## Публикация в GitHub

После инициализации репозитория:

```bash
git add .
git commit -m "Initial commit"
git remote add origin <your-repo-url>
git push -u origin main
```
