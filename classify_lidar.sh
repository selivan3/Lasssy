#!/bin/bash

# Lasssy V4 - Классификация с поддержкой изогнутых крыш
# Сохраняет ВСЕ точки, корректно классифицирует грунт, здания, растительность

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
    echo "[1/5] Конвертация..."
    run_lastool "txt2las64" -i "$input_file" -parse sxyz -set_scale 0.001 0.001 0.001 \
        -o "${TEMP_DIR}/${filename}_s1.laz"
    
    # Шаг 2: Шум (класс 7)
    echo "[2/5] Шум → класс 7..."
    run_lastool "lasnoise64" -i "${TEMP_DIR}/${filename}_s1.laz" \
        -step 4 -isolated 10 -classify_as 7 \
        -o "${TEMP_DIR}/${filename}_s2.laz" -demo
    
    # Шаг 3: Грунт (класс 2)
    echo "[3/5] Грунт → класс 2..."
    run_lastool "lasground64" -i "${TEMP_DIR}/${filename}_s2.laz" \
        -city -ignore_class 7 \
        -o "${TEMP_DIR}/${filename}_s3.laz" -demo
    
    # Шаг 4: Высоты + Здания (класс 6)
    echo "[4/5] Здания → класс 6..."
    run_lastool "lasheight64" -i "${TEMP_DIR}/${filename}_s3.laz" \
        -o "${TEMP_DIR}/${filename}_s4.laz" -demo
    
    run_lastool "lasclassify64" -i "${TEMP_DIR}/${filename}_s4.laz" \
        -planar 0.15 -rugged 0.4 -ground_offset 2.0 \
        -o "${TEMP_DIR}/${filename}_s5.laz" -demo
    
    # Шаг 5: Растительность - ТОЛЬКО для неклассифицированных (класс 1)
    echo "[5/5] Растительность → классы 3,4,5..."
    
    # Извлекаем неклассифицированные точки
    run_lastool "las2las64" -i "${TEMP_DIR}/${filename}_s5.laz" -keep_class 1 \
        -o "${TEMP_DIR}/${filename}_unclass.laz"
    
    # Классифицируем их по высоте
    run_lastool "lasheight64" -i "${TEMP_DIR}/${filename}_unclass.laz" \
        -classify_below 0 7 \
        -classify_between 0 0.5 3 \
        -classify_between 0.5 2 4 \
        -classify_above 2 5 \
        -o "${TEMP_DIR}/${filename}_veg.laz" -demo
    
    # Объединяем: грунт + здания + классифицированная растительность
    run_lastool "las2las64" -i "${TEMP_DIR}/${filename}_s5.laz" -drop_class 1 \
        -o "${TEMP_DIR}/${filename}_classified_part.laz"
    
    run_lastool "lasmerge64" \
        -i "${TEMP_DIR}/${filename}_classified_part.laz" \
        -i "${TEMP_DIR}/${filename}_veg.laz" \
        -o "${OUTPUT_DIR}/${filename}_classified.laz"
    
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
    
    if [[ "$input_count" -ne "$output_count" ]]; then
        echo "⚠️ Потеряно: $((input_count - output_count))"
    else
        echo "✓ Все сохранены"
    fi
    
    echo "Классы:"
    awk '{c[$1]++} END {for(k in c) printf "  %d: %d\n", k, c[k]}' "${OUTPUT_DIR}/${filename}_classified.xyz" | sort -t: -k1 -n
}

main() {
    echo "============================================="
    echo "  Lasssy V4 - Classification"
    echo "============================================="
    
    detect_os
    echo "ОС: $OS"
    
    if [[ "$OS" != "windows" ]] && ! command -v wine &> /dev/null; then
        echo "❌ Wine не найден"; exit 1
    fi
    
    mkdir -p "$OUTPUT_DIR" "$TEMP_DIR"
    
    for xyz_file in "${INPUT_DIR}"/*.xyz; do
        classify_file "$xyz_file"
        echo ""
    done
    
    rmdir "${TEMP_DIR}" 2>/dev/null || true
    echo "✓ Завершено!"
}

main "$@"
