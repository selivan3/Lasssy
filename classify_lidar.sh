#!/bin/bash

# Lasssy V3 - Кроссплатформенный классификатор LiDAR
# Поддержка: macOS, Linux, Windows (Git Bash/WSL)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INPUT_DIR="${SCRIPT_DIR}/datasets"
OUTPUT_DIR="${SCRIPT_DIR}/output"
TEMP_DIR="${SCRIPT_DIR}/temp"

# Определение ОС и настройка путей
detect_os() {
    case "$(uname -s)" in
        Darwin*)
            OS="macos"
            LASTOOLS_DIR="${SCRIPT_DIR}/lastools_win/LAStools/bin"
            RUN_PREFIX="wine"
            EXT=".exe"
            ;;
        Linux*)
            OS="linux"
            LASTOOLS_DIR="${SCRIPT_DIR}/lastools_win/LAStools/bin"
            RUN_PREFIX="wine"
            EXT=".exe"
            ;;
        MINGW*|MSYS*|CYGWIN*)
            OS="windows"
            LASTOOLS_DIR="${SCRIPT_DIR}/lastools_win/LAStools/bin"
            RUN_PREFIX=""
            EXT=".exe"
            ;;
        *)
            echo "Неизвестная ОС: $(uname -s)"
            exit 1
            ;;
    esac
    echo "Обнаружена ОС: $OS"
}

# Проверка зависимостей
check_dependencies() {
    echo "Проверка зависимостей..."
    
    if [[ "$OS" != "windows" ]]; then
        if ! command -v wine &> /dev/null; then
            echo ""
            echo "❌ Wine не установлен!"
            echo ""
            if [[ "$OS" == "macos" ]]; then
                echo "Установите Wine командой:"
                echo "  brew install --cask wine-stable"
            else
                echo "Установите Wine командой:"
                echo "  sudo apt install wine64  # Ubuntu/Debian"
                echo "  sudo dnf install wine    # Fedora"
            fi
            exit 1
        fi
        echo "✓ Wine установлен"
    fi
    
    if [[ ! -f "${LASTOOLS_DIR}/lasground64${EXT}" ]]; then
        echo ""
        echo "❌ LAStools не найдены!"
        echo ""
        echo "Скачайте LAStools:"
        echo "  ./download_lastools.sh"
        echo ""
        echo "Или вручную:"
        echo "  1. Скачайте: https://downloads.rapidlasso.de/LAStools.zip"
        echo "  2. Распакуйте в папку: lastools_win/"
        exit 1
    fi
    echo "✓ LAStools найдены"
}

# Запуск LAStools
run_lastool() {
    local tool="$1"
    shift
    
    if [[ -n "$RUN_PREFIX" ]]; then
        $RUN_PREFIX "${LASTOOLS_DIR}/${tool}${EXT}" "$@" 2>/dev/null
    else
        "${LASTOOLS_DIR}/${tool}${EXT}" "$@"
    fi
}

# Классификация одного файла
classify_file() {
    local input_file="$1"
    local filename=$(basename "$input_file" .xyz)
    
    echo "========================================="
    echo "Обработка: $filename"
    echo "========================================="
    
    # Шаг 1: XYZ → LAS
    echo "[1/6] Конвертация XYZ → LAS..."
    run_lastool "txt2las64" -i "$input_file" -parse sxyz -set_scale 0.001 0.001 0.001 -o "${TEMP_DIR}/${filename}_step1.laz"
    
    # Шаг 2: Шум (класс 7)
    echo "[2/6] Классификация шума..."
    run_lastool "lasnoise64" -i "${TEMP_DIR}/${filename}_step1.laz" -step 2 -isolated 5 -classify_as 7 -o "${TEMP_DIR}/${filename}_step2.laz" -demo
    
    # Шаг 3: Грунт (класс 2)
    echo "[3/6] Классификация грунта..."
    run_lastool "lasground64" -i "${TEMP_DIR}/${filename}_step2.laz" -wilderness -ignore_class 7 -o "${TEMP_DIR}/${filename}_step3.laz" -demo
    
    # Шаг 4: Высоты
    echo "[4/6] Расчёт высот..."
    run_lastool "lasheight64" -i "${TEMP_DIR}/${filename}_step3.laz" -replace_z -o "${TEMP_DIR}/${filename}_step4.laz" -demo
    
    # Шаг 5: Здания (класс 6)
    echo "[5/6] Классификация зданий..."
    run_lastool "lasclassify64" -i "${TEMP_DIR}/${filename}_step4.laz" -height_in_z -o "${TEMP_DIR}/${filename}_step5.laz" -demo
    
    # Шаг 6: Растительность (классы 3,4,5)
    echo "[6/6] Классификация растительности..."
    run_lastool "las2las64" -i "${TEMP_DIR}/${filename}_step5.laz" -keep_class 1 \
        -classify_z_between_as 0 0.5 3 -classify_z_between_as 0.5 2 4 -classify_z_between_as 2 100 5 \
        -o "${TEMP_DIR}/${filename}_veg.laz"
    
    run_lastool "lasmerge64" -i "${TEMP_DIR}/${filename}_step5.laz" -drop_class 1 \
        -i "${TEMP_DIR}/${filename}_veg.laz" -o "${OUTPUT_DIR}/${filename}_classified.laz"
    
    # Экспорт в XYZ и TXT
    run_lastool "las2txt64" -i "${OUTPUT_DIR}/${filename}_classified.laz" -parse cxyz -sep space -o "${OUTPUT_DIR}/${filename}_classified.xyz"
    run_lastool "las2txt64" -i "${OUTPUT_DIR}/${filename}_classified.laz" -parse cxyz -sep comma -o "${OUTPUT_DIR}/${filename}_classified.txt"
    
    # Очистка
    rm -f "${TEMP_DIR}/${filename}_"*.laz
    
    echo "✓ Готово: ${filename}"
}

# Главная функция
main() {
    echo "============================================="
    echo "  Lasssy V3 - LiDAR Classification"
    echo "  Кроссплатформенная версия"
    echo "============================================="
    echo ""
    
    detect_os
    check_dependencies
    
    mkdir -p "$OUTPUT_DIR" "$TEMP_DIR"
    
    local file_count=$(ls -1 "${INPUT_DIR}"/*.xyz 2>/dev/null | wc -l | tr -d ' ')
    echo ""
    echo "Найдено файлов: $file_count"
    echo ""
    
    if [[ $file_count -eq 0 ]]; then
        echo "❌ Нет XYZ файлов в ${INPUT_DIR}"
        exit 1
    fi
    
    local current=0
    for xyz_file in "${INPUT_DIR}"/*.xyz; do
        current=$((current + 1))
        echo ""
        echo "[$current/$file_count]"
        classify_file "$xyz_file"
    done
    
    rmdir "${TEMP_DIR}" 2>/dev/null || true
    
    echo ""
    echo "============================================="
    echo "  ✓ Классификация завершена!"
    echo "============================================="
    echo ""
    echo "Результаты в: ${OUTPUT_DIR}/"
    ls -lh "${OUTPUT_DIR}"/*.laz 2>/dev/null | head -10
}

main "$@"
