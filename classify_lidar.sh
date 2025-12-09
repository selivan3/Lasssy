#!/bin/bash

# Lasssy V4 - БЕЗОПАСНАЯ классификация без потери точек
# Простой и надёжный алгоритм

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INPUT_DIR="${SCRIPT_DIR}/datasets"
OUTPUT_DIR="${SCRIPT_DIR}/output"
TEMP_DIR="${SCRIPT_DIR}/temp"

detect_os() {
    case "$(uname -s)" in
        Darwin*) OS="macos"; LASTOOLS_DIR="${SCRIPT_DIR}/lastools_win/LAStools/bin"; RUN_PREFIX="wine"; EXT=".exe" ;;
        Linux*) OS="linux"; LASTOOLS_DIR="${SCRIPT_DIR}/lastools_win/LAStools/bin"; RUN_PREFIX="wine"; EXT=".exe" ;;
        MINGW*|MSYS*|CYGWIN*) OS="windows"; LASTOOLS_DIR="${SCRIPT_DIR}/lastools_win/LAStools/bin"; RUN_PREFIX=""; EXT=".exe" ;;
        *) echo "Неизвестная ОС"; exit 1 ;;
    esac
}

run_lastool() {
    local tool="$1"; shift
    if [[ -n "$RUN_PREFIX" ]]; then
        $RUN_PREFIX "${LASTOOLS_DIR}/${tool}${EXT}" "$@" 2>/dev/null
    else
        "${LASTOOLS_DIR}/${tool}${EXT}" "$@"
    fi
}

classify_file() {
    local input_file="$1"
    local filename=$(basename "$input_file" .xyz)
    
    echo "========================================="
    echo "Обработка: $filename"
    echo "========================================="
    
    local input_count=$(wc -l < "$input_file" | tr -d ' ')
    echo "Входных точек: $input_count"
    
    # Шаг 1: XYZ → LAS
    echo "[1/4] Конвертация..."
    run_lastool "txt2las64" -i "$input_file" -parse sxyz -set_scale 0.001 0.001 0.001 \
        -o "${TEMP_DIR}/${filename}_s1.laz"
    
    # Шаг 2: Шум (класс 7) - только классифицируем, не удаляем
    echo "[2/4] Шум → класс 7..."
    run_lastool "lasnoise64" -i "${TEMP_DIR}/${filename}_s1.laz" \
        -step 4 -isolated 10 -classify_as 7 \
        -o "${TEMP_DIR}/${filename}_s2.laz" -demo
    
    # Шаг 3: Грунт (класс 2)
    echo "[3/4] Грунт → класс 2..."
    run_lastool "lasground64" -i "${TEMP_DIR}/${filename}_s2.laz" \
        -wilderness -ignore_class 7 \
        -o "${TEMP_DIR}/${filename}_s3.laz" -demo
    
    # Шаг 4: Высоты + здания + растительность - ВСЁ В ОДНОМ ШАГЕ
    echo "[4/4] Классификация объектов..."
    
    # Сначала считаем высоты
    run_lastool "lasheight64" -i "${TEMP_DIR}/${filename}_s3.laz" \
        -o "${TEMP_DIR}/${filename}_s4.laz" -demo
    
    # Классифицируем здания (с параметрами для изогнутых крыш)
    run_lastool "lasclassify64" -i "${TEMP_DIR}/${filename}_s4.laz" \
        -planar 0.15 -rugged 0.4 -ground_offset 2.0 \
        -o "${TEMP_DIR}/${filename}_s5.laz" -demo
    
    # Классифицируем растительность по высоте
    # НЕ ИСПОЛЬЗУЕМ keep_class - это безопасно, просто ПЕРЕКЛАССИФИЦИРУЕТ неклассифицированные
    run_lastool "lasheight64" -i "${TEMP_DIR}/${filename}_s5.laz" \
        -classify_between 0 0.5 3 \
        -classify_between 0.5 2 4 \
        -classify_above 2 5 \
        -o "${OUTPUT_DIR}/${filename}_classified.laz" -demo
    
    # Экспорт
    echo "Экспорт..."
    run_lastool "las2txt64" -i "${OUTPUT_DIR}/${filename}_classified.laz" \
        -parse cxyz -sep space -o "${OUTPUT_DIR}/${filename}_classified.xyz"
    run_lastool "las2txt64" -i "${OUTPUT_DIR}/${filename}_classified.laz" \
        -parse cxyz -sep comma -o "${OUTPUT_DIR}/${filename}_classified.txt"
    
    # Очистка
    rm -f "${TEMP_DIR}/${filename}_"*.laz
    
    local output_count=$(wc -l < "${OUTPUT_DIR}/${filename}_classified.xyz" | tr -d ' ')
    echo "Выходных точек: $output_count"
    
    local diff=$((input_count - output_count))
    if [[ $diff -ne 0 ]]; then
        echo "⚠️ Потеряно: $diff точек"
    else
        echo "✓ Все точки сохранены"
    fi
    
    # Статистика
    echo "Классы:"
    awk '{c[$1]++} END {for(k in c) printf "  %d: %d\n", k, c[k]}' "${OUTPUT_DIR}/${filename}_classified.xyz" | sort -t: -k1 -n
}

main() {
    echo "============================================="
    echo "  Lasssy V4 - Safe Classification"
    echo "============================================="
    
    detect_os
    echo "ОС: $OS"
    
    if [[ "$OS" != "windows" ]] && ! command -v wine &> /dev/null; then
        echo "❌ Wine не найден"; exit 1
    fi
    
    mkdir -p "$OUTPUT_DIR" "$TEMP_DIR"
    
    local count=0
    for xyz_file in "${INPUT_DIR}"/*.xyz; do
        count=$((count + 1))
        echo ""
        echo "[$count/$(ls -1 "${INPUT_DIR}"/*.xyz | wc -l | tr -d ' ')]"
        classify_file "$xyz_file"
    done
    
    rmdir "${TEMP_DIR}" 2>/dev/null || true
    echo ""
    echo "✓ Завершено!"
}

main "$@"
