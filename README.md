# Lasssy V1 - LiDAR Classification Pipeline

Автоматическая классификация LiDAR данных на 6 классов с использованием LAStools.

## Классы

| Класс | Описание |
|-------|----------|
| 2 | Грунт |
| 3 | Низкая растительность (0-0.5м) |
| 4 | Средняя растительность (0.5-2м) |
| 5 | Высокая растительность (>2м) |
| 6 | Здания |
| 7 | Шум |

## Требования

- macOS/Linux
- Wine (для запуска LAStools)
- LAStools Windows binaries

## Установка

```bash
# Установка Wine (macOS)
brew install --cask wine-stable

# Скачивание LAStools
curl -L -o lastools.zip https://downloads.rapidlasso.de/LAStools.zip
unzip lastools.zip -d lastools_win
```

## Использование

### Классификация XYZ файлов

```bash
# Поместите *.xyz файлы в папку datasets/
./classify_lidar.sh
```

### Экспорт в другие форматы

```bash
./export_formats.sh
```

## Выходные форматы

| Формат | Содержимое |
|--------|------------|
| `.laz` | Сжатый LAS (бинарный) |
| `.xyz` | class x y z (пробел) |
| `.txt` | class,x,y,z (CSV) |

## Структура проекта

```
├── datasets/          # Входные XYZ файлы
├── output/            # Классифицированные результаты
├── classify_lidar.sh  # Скрипт классификации
├── export_formats.sh  # Скрипт экспорта
└── lastools_win/      # Windows LAStools (через Wine)
```

## Лицензия

DEMO режим LAStools - для production требуется лицензия от [rapidlasso](https://rapidlasso.de/pricing/).
