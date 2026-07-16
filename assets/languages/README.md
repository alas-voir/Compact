# Языковые пакеты Compact

Пакет перевода — JSON-файл с кодом, названием и словарём интерфейсных строк.
Пользовательские пакеты размещаются в `~/Library/Application Support/Compact/languages`
на macOS и автоматически появляются в настройках.

```json
{
  "code": "de",
  "name": "Deutsch",
  "translations": {
    "Настройки": "Einstellungen",
    "Закрыть": "Schließen"
  }
}
```

Отсутствующие строки остаются на русском языке.
