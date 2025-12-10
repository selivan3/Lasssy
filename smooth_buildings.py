#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Lasssy V4.1 - Умное сглаживание зданий (крыш) v2

Подход: Локальный анализ каждой точки
- Если точка окружена зданиями И находится высоко → конвертируем в здание
- Если точка часть вертикальной растительности (дерево) → НЕ конвертируем

Ключевые эвристики:
1. Крыша: точка высоко (>2м), рядом много зданий, мало связи с землёй
2. Дерево: под точкой есть растительность ниже (вертикальная структура)
"""

import sys
from collections import defaultdict, Counter
import math

# Константы классов
CLASS_GROUND = 2
CLASS_LOW_VEG = 3
CLASS_MED_VEG = 4
CLASS_HIGH_VEG = 5
CLASS_BUILDING = 6
CLASS_NOISE = 7

VEG_CLASSES = {CLASS_LOW_VEG, CLASS_MED_VEG, CLASS_HIGH_VEG}
NON_BUILDING = {CLASS_GROUND, CLASS_LOW_VEG, CLASS_MED_VEG, CLASS_HIGH_VEG}

def load_points(filepath):
    """Загрузка точек из XYZ файла"""
    points = []
    with open(filepath, 'r') as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) >= 4:
                cls = int(parts[0])
                x = float(parts[1])
                y = float(parts[2])
                z = float(parts[3])
                points.append({'class': cls, 'x': x, 'y': y, 'z': z})
    return points

def save_points(points, filepath):
    with open(filepath, 'w') as f:
        for p in points:
            f.write(f"{p['class']} {p['x']:.3f} {p['y']:.3f} {p['z']:.3f}\n")

def build_grid_2d(points, cell_size):
    """2D сетка для поиска соседей по XY"""
    grid = defaultdict(list)
    for i, p in enumerate(points):
        key = (int(p['x'] / cell_size), int(p['y'] / cell_size))
        grid[key].append(i)
    return grid

def get_column_neighbors(idx, points, grid, cell_size, xy_radius):
    """
    Получение всех точек в вертикальной колонне (по XY близко).
    Возвращает индексы точек над и под текущей.
    """
    p = points[idx]
    gx = int(p['x'] / cell_size)
    gy = int(p['y'] / cell_size)
    
    neighbors_above = []
    neighbors_below = []
    neighbors_same = []
    
    xy_radius_sq = xy_radius * xy_radius
    
    for dx in range(-1, 2):
        for dy in range(-1, 2):
            key = (gx + dx, gy + dy)
            if key in grid:
                for j in grid[key]:
                    if j == idx:
                        continue
                    q = points[j]
                    xy_dist_sq = (p['x'] - q['x'])**2 + (p['y'] - q['y'])**2
                    if xy_dist_sq <= xy_radius_sq:
                        z_diff = q['z'] - p['z']
                        if z_diff > 0.5:
                            neighbors_above.append(j)
                        elif z_diff < -0.5:
                            neighbors_below.append(j)
                        else:
                            neighbors_same.append(j)
    
    return neighbors_above, neighbors_below, neighbors_same

def analyze_point_context(idx, points, grid, cell_size, xy_radius):
    """
    Анализ контекста точки:
    - Сколько зданий рядом (на том же уровне)
    - Есть ли растительность ПОД этой точкой (признак дерева)
    - Есть ли связь с землёй снизу
    """
    above, below, same = get_column_neighbors(idx, points, grid, cell_size, xy_radius)
    
    # Классы на том же уровне
    same_classes = Counter(points[j]['class'] for j in same)
    building_count = same_classes.get(CLASS_BUILDING, 0)
    veg_count = sum(same_classes.get(c, 0) for c in VEG_CLASSES)
    total_same = len(same)
    
    # Классы НИЖЕ
    below_classes = Counter(points[j]['class'] for j in below)
    veg_below = sum(below_classes.get(c, 0) for c in VEG_CLASSES)
    ground_below = below_classes.get(CLASS_GROUND, 0)
    building_below = below_classes.get(CLASS_BUILDING, 0)
    total_below = len(below)
    
    # Классы ВЫШЕ
    above_classes = Counter(points[j]['class'] for j in above)
    total_above = len(above)
    
    return {
        'building_same': building_count,
        'veg_same': veg_count,
        'total_same': total_same,
        'veg_below': veg_below,
        'ground_below': ground_below,
        'building_below': building_below,
        'total_below': total_below,
        'total_above': total_above
    }

def should_be_building(point, context, min_building_neighbors=3):
    """
    Определяет, должна ли точка быть зданием.
    
    Условия для конверсии в здание:
    1. Точка уже не здание (растительность/грунт)
    2. Рядом на том же уровне есть здания
    3. Под точкой НЕТ растительности (иначе это дерево)
    4. Точка достаточно высоко
    """
    if point['class'] == CLASS_BUILDING:
        return False  # Уже здание
    
    if point['class'] == CLASS_NOISE:
        return False  # Шум не трогаем
    
    z = point['z']
    
    # Слишком низко для крыши
    if z < 1.5:
        return False
    
    # Рядом должны быть здания
    if context['building_same'] < min_building_neighbors:
        return False
    
    # Проверка на дерево: если под нами много растительности → дерево
    if context['veg_below'] > 2:
        return False
    
    # Проверка: если зданий рядом больше чем растительности
    total_same = context['total_same']
    if total_same > 0:
        building_ratio = context['building_same'] / total_same
        if building_ratio < 0.3:
            return False
    
    # Дополнительная проверка: если под нами здание, это точно крыша
    if context['building_below'] > 0:
        return True
    
    # Если нет растительности снизу и рядом здания → крыша
    if context['veg_below'] == 0 and context['building_same'] >= min_building_neighbors:
        return True
    
    return False

def smooth_buildings(points, xy_radius=2.0, min_building_neighbors=3):
    """
    Умное сглаживание зданий.
    """
    cell_size = xy_radius * 1.5
    
    print(f"Параметры: xy_радиус={xy_radius}м, мин.соседей={min_building_neighbors}")
    print(f"Построение 2D сетки...")
    grid = build_grid_2d(points, cell_size)
    
    # Начальная статистика
    initial = Counter(p['class'] for p in points)
    print(f"\nНачальное распределение:")
    print(f"  Здания (6): {initial.get(CLASS_BUILDING, 0):,}")
    print(f"  Высокая раст. (5): {initial.get(CLASS_HIGH_VEG, 0):,}")
    print(f"  Средняя раст. (4): {initial.get(CLASS_MED_VEG, 0):,}")
    print(f"  Низкая раст. (3): {initial.get(CLASS_LOW_VEG, 0):,}")
    print(f"  Грунт (2): {initial.get(CLASS_GROUND, 0):,}")
    
    # Анализ и конверсия
    converted = 0
    protected_trees = 0
    
    print(f"\nАнализ {len(points):,} точек...")
    
    for i, p in enumerate(points):
        if p['class'] in NON_BUILDING:
            context = analyze_point_context(i, points, grid, cell_size, xy_radius)
            
            if should_be_building(p, context, min_building_neighbors):
                points[i]['class'] = CLASS_BUILDING
                converted += 1
            elif context['veg_below'] > 2 and p['class'] in VEG_CLASSES:
                # Точка часть дерева - защищаем
                protected_trees += 1
        
        if i % 50000 == 0 and i > 0:
            print(f"  Обработано: {i:,}/{len(points):,}, конверсий: {converted:,}")
    
    # Финальная статистика
    final = Counter(p['class'] for p in points)
    print(f"\nФинальное распределение:")
    print(f"  Здания (6): {final.get(CLASS_BUILDING, 0):,} (+{final.get(CLASS_BUILDING, 0) - initial.get(CLASS_BUILDING, 0):,})")
    print(f"  Высокая раст. (5): {final.get(CLASS_HIGH_VEG, 0):,}")
    print(f"  Средняя раст. (4): {final.get(CLASS_MED_VEG, 0):,}")
    print(f"  Низкая раст. (3): {final.get(CLASS_LOW_VEG, 0):,}")
    print(f"  Грунт (2): {final.get(CLASS_GROUND, 0):,}")
    
    print(f"\n{'='*50}")
    print(f"Конвертировано в здания: {converted:,} точек")
    print(f"Защищено как деревья: {protected_trees:,} точек")
    
    return points

def main():
    if len(sys.argv) < 2:
        print("Lasssy V4.1 - Умное сглаживание зданий v2")
        print("-" * 50)
        print("Использование:")
        print("  python smooth_buildings.py <input.xyz> [output.xyz] [опции]")
        print("")
        print("Опции:")
        print("  --radius=N   XY радиус поиска соседей (по умолчанию 2.0)")
        print("  --min=N      Мин. соседей-зданий для конверсии (по умолчанию 3)")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = None
    radius = 2.0
    min_neighbors = 3
    
    for arg in sys.argv[2:]:
        if arg.startswith('--radius='):
            radius = float(arg.split('=')[1])
        elif arg.startswith('--min='):
            min_neighbors = int(arg.split('=')[1])
        elif not arg.startswith('--'):
            output_file = arg
    
    if output_file is None:
        output_file = input_file.replace('.xyz', '_building_smoothed.xyz')
    
    print("=" * 50)
    print("  Lasssy V4.1 - Умное сглаживание зданий v2")
    print("=" * 50)
    
    print(f"\nЗагрузка: {input_file}")
    points = load_points(input_file)
    print(f"Всего точек: {len(points):,}")
    
    print(f"\nОбработка...")
    points = smooth_buildings(points, xy_radius=radius, min_building_neighbors=min_neighbors)
    
    print(f"\nСохранение: {output_file}")
    save_points(points, output_file)
    print("✓ Готово!")

if __name__ == "__main__":
    main()
