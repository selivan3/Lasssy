# Lasssy - LiDAR Classification Pipeline

Автоматическая классификация LiDAR данных на 6 классов с визуальным редактором для ручной корректировки.

## 🎯 Возможности

- Автоматическая классификация на 6 классов
- Визуальный 3D редактор для ручной корректировки
- Семантическое выделение объектов (здания, деревья)
- Экспорт в форматы: LAZ, XYZ, TXT

## 📊 Классы

| Класс | Описание |
|-------|----------|
| 2 | Грунт |
| 3 | Низкая растительность (0-0.5м) |
| 4 | Средняя растительность (0.5-2м) |
| 5 | Высокая растительность (>2м) |
| 6 | Здания |
| 7 | Шум |

---

## 🖥️ Установка

### Windows

1. **Скачать LAStools:**
   ```cmd
   :: Скачайте вручную: https://downloads.rapidlasso.de/LAStools.zip
   :: Распакуйте в папку: lastools_win/
   ```

2. **Готово!** Wine не нужен.

### macOS

1. **Установить Wine:**
   ```bash
   brew install --cask wine-stable
   ```

2. **Скачать LAStools:**
   ```bash
   chmod +x download_lastools.sh
   ./download_lastools.sh
   ```

### Linux (Ubuntu/Debian)

1. **Установить Wine:**
   ```bash
   sudo apt update
   sudo apt install wine64 unzip curl
   ```

2. **Скачать LAStools:**
   ```bash
   chmod +x download_lastools.sh
   ./download_lastools.sh
   ```

### Linux (Fedora)

1. **Установить Wine:**
   ```bash
   sudo dnf install wine unzip curl
   ```

2. **Скачать LAStools:**
   ```bash
   chmod +x download_lastools.sh
   ./download_lastools.sh
   ```

---

## 🚀 Использование

### Автоматическая классификация

#### Windows:
```cmd
:: Поместите *.xyz файлы в папку datasets/
classify_lidar.bat
```

#### macOS / Linux:
```bash
# Поместите *.xyz файлы в папку datasets/
chmod +x classify_lidar.sh
./classify_lidar.sh
```

### Визуальный редактор

1. Откройте `editor.html` в браузере
2. Загрузите файл из `output/`
3. Кликните на объект — выделится весь связанный сегмент
4. Выберите целевой класс (2-7)
5. Нажмите Enter для применения
6. Сохраните результат

---

## 📁 Структура проекта

```
Lasssy/
├── datasets/              # Входные XYZ файлы
├── output/                # Результаты классификации
├── classify_lidar.sh      # Скрипт для macOS/Linux
├── classify_lidar.bat     # Скрипт для Windows
├── download_lastools.sh   # Загрузка LAStools
├── editor.html            # Визуальный 3D редактор
└── lastools_win/          # LAStools (скачивается)
```

---

## 📖 Формат файлов

### Входной формат (XYZ):
```
index x y z
0 51.764 83.025 -1.48
0 84.503 16.874 5.06
```

### Выходной формат:
```
class x y z
2 51.764 83.025 0.000
6 84.503 16.874 5.060
```

---

## ⚠️ Примечания

- LAStools работает в **DEMO режиме** (бесплатно до 1.5M точек)
- Для production нужна [лицензия](https://rapidlasso.de/pricing/)
- Редактор работает в любом современном браузере

---

## 📜 Лицензия

MIT License. LAStools © rapidlasso GmbH.
