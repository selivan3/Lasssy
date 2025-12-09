#!/bin/bash

# Экспорт классифицированных LAZ файлов в XYZ и TXT форматы
# Вход: output/*.laz
# Выход: output/*.xyz, output/*.txt

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUTPUT_DIR="${SCRIPT_DIR}/output"
WIN_BIN_DIR="${SCRIPT_DIR}/lastools_win/LAStools/bin"

echo "============================================="
echo "  Экспорт в дополнительные форматы"
echo "  LAZ → XYZ, TXT"
echo "============================================="
echo ""

# Функция запуска LAStools через Wine
run_lastool() {
    local tool="$1"
    shift
    wine "${WIN_BIN_DIR}/${tool}" "$@" 2>/dev/null
}

# Подсчёт файлов
file_count=$(ls -1 "${OUTPUT_DIR}"/*_classified.laz 2>/dev/null | wc -l | tr -d ' ')
echo "Найдено LAZ файлов: $file_count"
echo ""

if [[ $file_count -eq 0 ]]; then
    echo "ОШИБКА: Нет LAZ файлов в ${OUTPUT_DIR}"
    exit 1
fi

current=0
for laz_file in "${OUTPUT_DIR}"/*_classified.laz; do
    current=$((current + 1))
    filename=$(basename "$laz_file" .laz)
    
    echo "[$current/$file_count] Экспорт: $filename"
    
    # Экспорт в XYZ формат (x y z classification)
    echo "  → XYZ..."
    run_lastool "las2txt64.exe" \
        -i "$laz_file" \
        -parse xyzc \
        -sep space \
        -o "${OUTPUT_DIR}/${filename}.xyz"
    
    # Экспорт в TXT формат (x y z classification с заголовком)
    echo "  → TXT..."
    run_lastool "las2txt64.exe" \
        -i "$laz_file" \
        -parse xyzc \
        -sep comma \
        -header \
        -o "${OUTPUT_DIR}/${filename}.txt"
    
    echo "  ✓ Готово"
done

echo ""
echo "============================================="
echo "  Экспорт завершён!"
echo "============================================="
echo ""
echo "Файлы:"
ls -lh "${OUTPUT_DIR}"/*.laz "${OUTPUT_DIR}"/*.xyz "${OUTPUT_DIR}"/*.txt 2>/dev/null | head -30
