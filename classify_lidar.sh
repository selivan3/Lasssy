#!/bin/bash

# LiDAR Classification Script with Wine (for macOS)
# Классификация точек на 6 классов (DEMO режим - до 1.5M точек):
# 2 - Грунт
# 3 - Низкая растительность (0-0.5м)
# 4 - Средняя растительность (0.5-2м)
# 5 - Высокая растительность (>2м)
# 6 - Здания
# 7 - Шум

# Директории
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INPUT_DIR="${SCRIPT_DIR}/datasets"
OUTPUT_DIR="${SCRIPT_DIR}/output"
TEMP_DIR="${SCRIPT_DIR}/temp"
WIN_BIN_DIR="${SCRIPT_DIR}/lastools_win/LAStools/bin"

# Создание директорий
mkdir -p "$OUTPUT_DIR"
mkdir -p "$TEMP_DIR"

# Функция запуска LAStools через Wine (подавляем stderr)
run_lastool() {
    local tool="$1"
    shift
    wine "${WIN_BIN_DIR}/${tool}" "$@" 2>/dev/null
}

# Функция классификации одного файла
classify_file() {
    local input_file="$1"
    local filename=$(basename "$input_file" .xyz)
    
    echo "========================================="
    echo "Обработка: $filename"
    echo "========================================="
    
    # Шаг 1: Конвертация XYZ → LAS (open-source)
    echo "[1/6] Конвертация XYZ → LAS..."
    run_lastool "txt2las64.exe" \
        -i "$input_file" \
        -parse sxyz \
        -set_scale 0.001 0.001 0.001 \
        -o "${TEMP_DIR}/${filename}_step1.laz"
    
    if [[ ! -f "${TEMP_DIR}/${filename}_step1.laz" ]]; then
        echo "ОШИБКА: Не удалось создать LAS файл"
        return 1
    fi
    
    # Шаг 2: Удаление шума (Класс 7) - DEMO режим
    echo "[2/6] Классификация шума (класс 7)..."
    run_lastool "lasnoise64.exe" \
        -i "${TEMP_DIR}/${filename}_step1.laz" \
        -step 2 \
        -isolated 5 \
        -classify_as 7 \
        -o "${TEMP_DIR}/${filename}_step2.laz" \
        -demo
    
    # Шаг 3: Классификация грунта (Класс 2) - DEMO режим
    echo "[3/6] Классификация грунта (класс 2)..."
    run_lastool "lasground64.exe" \
        -i "${TEMP_DIR}/${filename}_step2.laz" \
        -wilderness \
        -ignore_class 7 \
        -o "${TEMP_DIR}/${filename}_step3.laz" \
        -demo
    
    # Шаг 4: Расчёт высот над землёй - DEMO режим
    echo "[4/6] Расчёт высот над землёй..."
    run_lastool "lasheight64.exe" \
        -i "${TEMP_DIR}/${filename}_step3.laz" \
        -replace_z \
        -o "${TEMP_DIR}/${filename}_step4.laz" \
        -demo
    
    # Шаг 5: Классификация зданий (Класс 6) - DEMO режим
    echo "[5/6] Классификация зданий (класс 6)..."
    run_lastool "lasclassify64.exe" \
        -i "${TEMP_DIR}/${filename}_step4.laz" \
        -height_in_z \
        -o "${TEMP_DIR}/${filename}_step5.laz" \
        -demo
    
    # Шаг 6: Классификация растительности по высоте (только для класса 1 - unclassified)
    echo "[6/6] Классификация растительности (классы 3, 4, 5)..."
    run_lastool "las2las64.exe" \
        -i "${TEMP_DIR}/${filename}_step5.laz" \
        -keep_class 1 \
        -classify_z_between_as 0 0.5 3 \
        -classify_z_between_as 0.5 2 4 \
        -classify_z_between_as 2 100 5 \
        -o "${TEMP_DIR}/${filename}_veg.laz"
    
    # Объединяем грунт/здания с классифицированной растительностью
    run_lastool "lasmerge64.exe" \
        -i "${TEMP_DIR}/${filename}_step5.laz" \
        -drop_class 1 \
        -i "${TEMP_DIR}/${filename}_veg.laz" \
        -o "${OUTPUT_DIR}/${filename}_classified.laz"
    
    # Очистка временных файлов
    rm -f "${TEMP_DIR}/${filename}_step"*.laz "${TEMP_DIR}/${filename}_veg.laz"
    
    if [[ -f "${OUTPUT_DIR}/${filename}_classified.laz" ]]; then
        echo "✓ Завершено: ${filename}_classified.laz"
    else
        echo "✗ Ошибка: файл не создан"
    fi
    echo ""
}

# Основной скрипт
main() {
    echo "============================================="
    echo "  LiDAR Classification Pipeline"
    echo "  LAStools + Wine on macOS (DEMO mode)"
    echo "============================================="
    echo ""
    echo "ВНИМАНИЕ: DEMO режим - возможны артефакты на выводе"
    echo ""
    
    # Проверка Wine
    if ! command -v wine &> /dev/null; then
        echo "ОШИБКА: Wine не установлен"
        exit 1
    fi
    
    # Проверка Windows LAStools
    if [[ ! -f "${WIN_BIN_DIR}/lasground64.exe" ]]; then
        echo "ОШИБКА: Windows LAStools не найдены"
        exit 1
    fi
    
    # Подсчёт файлов
    file_count=$(ls -1 "${INPUT_DIR}"/*.xyz 2>/dev/null | wc -l | tr -d ' ')
    echo "Найдено файлов: $file_count"
    echo ""
    
    if [[ $file_count -eq 0 ]]; then
        echo "ОШИБКА: Нет XYZ файлов в ${INPUT_DIR}"
        exit 1
    fi
    
    # Обработка каждого файла
    current=0
    for xyz_file in "${INPUT_DIR}"/*.xyz; do
        current=$((current + 1))
        echo "[$current/$file_count]"
        classify_file "$xyz_file"
    done
    
    # Очистка
    rmdir "${TEMP_DIR}" 2>/dev/null
    
    echo "============================================="
    echo "  Классификация завершена!"
    echo "============================================="
    echo ""
    ls -lh "${OUTPUT_DIR}"/*.laz 2>/dev/null || echo "Нет выходных файлов"
}

main "$@"
