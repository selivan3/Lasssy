#!/bin/bash

# Скрипт загрузки LAStools
# Работает на macOS, Linux, Windows (Git Bash)

echo "Загрузка LAStools..."

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Скачивание
if command -v curl &> /dev/null; then
    curl -L -o lastools.zip "https://downloads.rapidlasso.de/LAStools.zip"
elif command -v wget &> /dev/null; then
    wget -O lastools.zip "https://downloads.rapidlasso.de/LAStools.zip"
else
    echo "❌ Нужен curl или wget для загрузки"
    exit 1
fi

# Распаковка
echo "Распаковка..."
if command -v unzip &> /dev/null; then
    unzip -o lastools.zip -d lastools_win
else
    echo "❌ Нужен unzip для распаковки"
    exit 1
fi

rm lastools.zip
echo "✓ LAStools установлены в lastools_win/"
