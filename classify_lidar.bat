@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

:: Lasssy V3 - Windows Native Script
:: Классификация LiDAR данных

echo =============================================
echo   Lasssy V3 - LiDAR Classification
echo   Windows Native
echo =============================================
echo.

set "SCRIPT_DIR=%~dp0"
set "INPUT_DIR=%SCRIPT_DIR%datasets"
set "OUTPUT_DIR=%SCRIPT_DIR%output"
set "TEMP_DIR=%SCRIPT_DIR%temp"
set "LASTOOLS_DIR=%SCRIPT_DIR%lastools_win\LAStools\bin"

:: Проверка LAStools
if not exist "%LASTOOLS_DIR%\lasground64.exe" (
    echo.
    echo ❌ LAStools не найдены!
    echo.
    echo Скачайте LAStools:
    echo   1. https://downloads.rapidlasso.de/LAStools.zip
    echo   2. Распакуйте в папку: lastools_win\
    echo.
    pause
    exit /b 1
)

:: Создание директорий
if not exist "%OUTPUT_DIR%" mkdir "%OUTPUT_DIR%"
if not exist "%TEMP_DIR%" mkdir "%TEMP_DIR%"

:: Подсчёт файлов
set count=0
for %%f in ("%INPUT_DIR%\*.xyz") do set /a count+=1

echo Найдено файлов: %count%
echo.

if %count%==0 (
    echo ❌ Нет XYZ файлов в %INPUT_DIR%
    pause
    exit /b 1
)

:: Обработка файлов
set current=0
for %%f in ("%INPUT_DIR%\*.xyz") do (
    set /a current+=1
    set "filename=%%~nf"
    
    echo.
    echo [!current!/%count%] =========================================
    echo Обработка: !filename!
    echo =========================================
    
    echo [1/6] Конвертация XYZ - LAS...
    "%LASTOOLS_DIR%\txt2las64.exe" -i "%%f" -parse sxyz -set_scale 0.001 0.001 0.001 -o "%TEMP_DIR%\!filename!_step1.laz"
    
    echo [2/6] Классификация шума...
    "%LASTOOLS_DIR%\lasnoise64.exe" -i "%TEMP_DIR%\!filename!_step1.laz" -step 2 -isolated 5 -classify_as 7 -o "%TEMP_DIR%\!filename!_step2.laz" -demo
    
    echo [3/6] Классификация грунта...
    "%LASTOOLS_DIR%\lasground64.exe" -i "%TEMP_DIR%\!filename!_step2.laz" -wilderness -ignore_class 7 -o "%TEMP_DIR%\!filename!_step3.laz" -demo
    
    echo [4/6] Расчёт высот...
    "%LASTOOLS_DIR%\lasheight64.exe" -i "%TEMP_DIR%\!filename!_step3.laz" -replace_z -o "%TEMP_DIR%\!filename!_step4.laz" -demo
    
    echo [5/6] Классификация зданий...
    "%LASTOOLS_DIR%\lasclassify64.exe" -i "%TEMP_DIR%\!filename!_step4.laz" -height_in_z -o "%TEMP_DIR%\!filename!_step5.laz" -demo
    
    echo [6/6] Классификация растительности...
    "%LASTOOLS_DIR%\las2las64.exe" -i "%TEMP_DIR%\!filename!_step5.laz" -keep_class 1 -classify_z_between_as 0 0.5 3 -classify_z_between_as 0.5 2 4 -classify_z_between_as 2 100 5 -o "%TEMP_DIR%\!filename!_veg.laz"
    
    "%LASTOOLS_DIR%\lasmerge64.exe" -i "%TEMP_DIR%\!filename!_step5.laz" -drop_class 1 -i "%TEMP_DIR%\!filename!_veg.laz" -o "%OUTPUT_DIR%\!filename!_classified.laz"
    
    :: Экспорт
    "%LASTOOLS_DIR%\las2txt64.exe" -i "%OUTPUT_DIR%\!filename!_classified.laz" -parse cxyz -sep space -o "%OUTPUT_DIR%\!filename!_classified.xyz"
    "%LASTOOLS_DIR%\las2txt64.exe" -i "%OUTPUT_DIR%\!filename!_classified.laz" -parse cxyz -sep comma -o "%OUTPUT_DIR%\!filename!_classified.txt"
    
    :: Очистка
    del /q "%TEMP_DIR%\!filename!_*.laz" 2>nul
    
    echo ✓ Готово: !filename!
)

rmdir "%TEMP_DIR%" 2>nul

echo.
echo =============================================
echo   ✓ Классификация завершена!
echo =============================================
echo.
echo Результаты в: %OUTPUT_DIR%\
echo.

dir /b "%OUTPUT_DIR%\*.laz"

pause
