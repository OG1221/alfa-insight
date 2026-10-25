# Запуск на Windows

Docker Compose остаётся основным воспроизводимым способом сдачи. Если Docker недоступен, можно использовать отдельный PostgreSQL без установки системной службы.

Нужны Python 3.12, Node 22+, pnpm 11.25.0, Windows x64 PostgreSQL 16 или 17. Бинарный архив PostgreSQL доступен на официальной странице EDB: https://www.enterprisedb.com/download-postgresql-binaries . Не копируйте базу macOS и .venv с другой системы.

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r backend/requirements.lock.txt
pnpm --dir frontend install --frozen-lockfile
pnpm --dir frontend build
./scripts/start-windows.ps1 -PythonExe "$PWD/.venv/Scripts/python.exe" -PgBin 'D:/tools/pgsql/bin' -DataDirectory 'D:/alfa-data' -SkipBuild
```

База слушает только 127.0.0.1. Trust-аутентификация предназначена исключительно для локальной разработки. Для внешнего размещения используйте пароль PostgreSQL и настройки доступа из docs/deployment.md.

Остановка локальной базы: pg_ctl.exe -D D:/alfa-data -m fast stop. Это не удаляет данные.

Импорт официального набора выполняется отдельно по README; параметры API задаются только в серверном .env. Сам ключ в интерфейс не передается. Для OCR сканированных PDF на Windows нужен Tesseract с языками rus+eng. Наличие runtime/ocr_macos не включает его на Windows.
