#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Lasssy V4.1 - Улучшенное сглаживание зданий v3

НОВЫЕ ЭВРИСТИКИ:
1. Если над точкой есть здание (крыша), а точка вертикально под ней → стена здания
2. Вертикальные структуры (резкий подъём) = здание или дерево
3. Грунт не может резко подниматься вверх (кроме ям)
4. Если кластер точек квадратный/прямоугольный → здание

Алгоритм:
- Для каждой точки проверяем: есть ли здание ВЫШЕ
- Если да, и точка входит в вертикальный коридор → это стена здания
"""

import sys
from collections import defaultdict, Counter
import math

CLASS_GROUND = 2
CLASS_LOW_VEG = 3
CLASS_MED_VEG = 4
CLASS_HIGH_VEG = 5
CLASS_BUILDING = 6
CLASS_NOISE = 7

VEG_CLASSES = {CLASS_LOW_VEG, CLASS_MED_VEG, CLASS_HIGH_VEG}
NON_BUILDING = {CLASS_GROUND, CLASS_LOW_VEG, CLASS_MED_VEG, CLASS_HIGH_VEG}

def load_points(filepath):
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
    """2D сетка для быстрого поиска по XY"""
    grid = defaultdict(list)
    for i, p in enumerate(points):
        key = (int(p['x'] / cell_size), int(p['y'] / cell_size))
        grid[key].append(i)
    return grid

def get_vertical_column(x, y, points, grid, cell_size, xy_radius):
    """Получить все точки в вертикальной колонне над и под заданной позицией"""
    gx = int(x / cell_size)
    gy = int(y / cell_size)
    
    column_points = []
    xy_radius_sq = xy_radius * xy_radius
    
    for dx in range(-1, 2):
        for dy in range(-1, 2):
            key = (gx + dx, gy + dy)
            if key in grid:
                for idx in grid[key]:
                    p = points[idx]
                    dist_sq = (x - p['x'])**2 + (y - p['y'])**2
                    if dist_sq <= xy_radius_sq:
                        column_points.append(idx)
    
    return column_points

def analyze_vertical_structure(idx, points, grid, cell_size, xy_radius):
    """
    Анализ вертикальной структуры над/под точкой.
    Возвращает информацию о наличии зданий выше.
    """
    p = points[idx]
    column = get_vertical_column(p['x'], p['y'], points, grid, cell_size, xy_radius)
    
    buildings_above = []
    buildings_below = []
    buildings_same_level = []
    all_above = []
    all_below = []
    
    z_tolerance = 0.5
    
    for j in column:
        if j == idx:
            continue
        q = points[j]
        z_diff = q['z'] - p['z']
        
        if z_diff > z_tolerance:
            all_above.append(j)
            if q['class'] == CLASS_BUILDING:
                buildings_above.append(j)
        elif z_diff < -z_tolerance:
            all_below.append(j)
            if q['class'] == CLASS_BUILDING:
                buildings_below.append(j)
        else:
            if q['class'] == CLASS_BUILDING:
                buildings_same_level.append(j)
    
    # Найти максимальную высоту здания над текущей точкой
    max_building_z = 0
    if buildings_above:
        max_building_z = max(points[j]['z'] for j in buildings_above)
    
    return {
        'buildings_above': len(buildings_above),
        'buildings_below': len(buildings_below),
        'buildings_same': len(buildings_same_level),
        'total_above': len(all_above),
        'total_below': len(all_below),
        'max_building_z': max_building_z,
        'column_size': len(column)
    }

def is_vertical_wall(idx, points, grid, cell_size, xy_radius):
    """
    Проверка: является ли точка частью вертикальной стены здания.
    
    Критерии:
    1. Есть здание ВЫШЕ (крыша)
    2. Точка находится в вертикальном коридоре под зданием
    3. Нет растительности, соединяющей с землёй (как у дерева)
    """
    p = points[idx]
    
    # Точка уже здание - пропускаем
    if p['class'] == CLASS_BUILDING:
        return False
    
    analysis = analyze_vertical_structure(idx, points, grid, cell_size, xy_radius)
    
    # Критерий 1: Есть здания ВЫШЕ (крыша)
    if analysis['buildings_above'] == 0:
        return False
    
    # Критерий 2: Над нами значительно больше зданий чем других точек
    building_ratio_above = 0
    if analysis['total_above'] > 0:
        building_ratio_above = analysis['buildings_above'] / analysis['total_above']
    
    # Если большая часть точек выше - здания → это стена
    if building_ratio_above >= 0.3:
        return True
    
    # Критерий 3: Рядом на том же уровне есть здания
    if analysis['buildings_same'] >= 2:
        return True
    
    return False

def is_vertical_ground(idx, points, grid, cell_size, xy_radius, min_height=2.0, min_points_above=5):
    """
    Проверка: является ли грунт вертикальным (идёт вверх как стена).
    Вертикальный грунт - это ошибка, его нужно пометить как высокую растительность.
    
    НО: грунт ВНИЗУ (у основания) должен оставаться грунтом!
    Требуем много точек над текущей - иначе это просто обычный грунт.
    """
    p = points[idx]
    
    if p['class'] != CLASS_GROUND:
        return False
    
    # ВАЖНО: грунт внизу (низкая высота) должен оставаться грунтом
    # Ищем локальный минимум Z в колонне
    column = get_vertical_column(p['x'], p['y'], points, grid, cell_size, xy_radius)
    if column:
        min_z = min(points[j]['z'] for j in column)
        height_above_base = p['z'] - min_z
        
        # Если точка низко (менее min_height над основанием) - это нормальный грунт
        if height_above_base < min_height:
            return False
    
    analysis = analyze_vertical_structure(idx, points, grid, cell_size, xy_radius)
    
    # Вертикальный грунт: МНОГО точек над текущей (вертикальная структура)
    # Если мало точек сверху - это просто обычный грунт
    if analysis['total_above'] >= min_points_above:
        return True
    
    return False

def is_isolated_high_veg(idx, points, grid, cell_size, xy_radius, min_ground_ratio=0.5):
    """
    Проверка: является ли высокая растительность ошибочной.
    
    Критерии:
    1. Окружена грунтом и не идёт вверх → грунт
    2. Под низкой или средней растительностью → грунт (так не бывает!)
    """
    p = points[idx]
    
    if p['class'] != CLASS_HIGH_VEG:
        return False
    
    # Получаем соседей на том же уровне и выше
    column = get_vertical_column(p['x'], p['y'], points, grid, cell_size, xy_radius)
    
    same_level = []
    above = []
    low_med_above = 0  # Низкая или средняя растительность выше
    z_tolerance = 0.5
    
    for j in column:
        if j == idx:
            continue
        q = points[j]
        z_diff = q['z'] - p['z']
        
        if abs(z_diff) <= z_tolerance:
            same_level.append(j)
        elif z_diff > z_tolerance:
            above.append(j)
            # Проверяем: есть ли низкая/средняя растительность ВЫШЕ
            if q['class'] in {CLASS_LOW_VEG, CLASS_MED_VEG}:
                low_med_above += 1
    
    # КРИТЕРИЙ 2: Если над высокой растительностью есть низкая/средняя → это грунт!
    if low_med_above >= 1:
        return True
    
    # Если есть много точек ВЫШЕ - это настоящая вертикальная структура (дерево)
    if len(above) >= 3:
        return False
    
    # Подсчитываем соседей на том же уровне
    if len(same_level) < 2:
        # Мало соседей - не можем определить
        return False
    
    ground_neighbors = sum(1 for j in same_level if points[j]['class'] == CLASS_GROUND)
    ground_ratio = ground_neighbors / len(same_level)
    
    # КРИТЕРИЙ 1: Если большинство соседей - грунт → это тоже грунт
    if ground_ratio >= min_ground_ratio:
        return True
    
    return False

def smooth_buildings_v3(points, xy_radius=1.5, min_buildings_above=2):
    """
    Улучшенное сглаживание зданий:
    - Обнаружение вертикальных стен (точки под крышей)
    - Вертикальный грунт → высокая растительность
    """
    cell_size = xy_radius * 2
    
    print(f"Параметры: xy_радиус={xy_radius}м")
    print(f"Построение 2D сетки...")
    grid = build_grid_2d(points, cell_size)
    
    initial = Counter(p['class'] for p in points)
    print(f"\nНачальное распределение:")
    print(f"  Здания (6): {initial.get(CLASS_BUILDING, 0):,}")
    print(f"  Грунт (2): {initial.get(CLASS_GROUND, 0):,}")
    print(f"  Высокая раст. (5): {initial.get(CLASS_HIGH_VEG, 0):,}")
    
    walls_converted = 0
    vertical_ground_fixed = 0
    isolated_veg_fixed = 0
    
    print(f"\nЭтап 1: Поиск стен зданий и вертикального грунта...")
    
    for i, p in enumerate(points):
        # Растительность под зданием → стена здания
        if p['class'] in VEG_CLASSES:
            if is_vertical_wall(i, points, grid, cell_size, xy_radius):
                points[i]['class'] = CLASS_BUILDING
                walls_converted += 1
        # Вертикальный грунт → высокая растительность
        elif p['class'] == CLASS_GROUND:
            if is_vertical_ground(i, points, grid, cell_size, xy_radius):
                points[i]['class'] = CLASS_HIGH_VEG
                vertical_ground_fixed += 1
        
        if i % 20000 == 0 and i > 0:
            print(f"  Обработано: {i:,}/{len(points):,}")
    
    print(f"\nЭтап 2: Исправление изолированной высокой растительности...")
    
    for i, p in enumerate(points):
        # Высокая растительность, окружённая грунтом → грунт
        if p['class'] == CLASS_HIGH_VEG:
            if is_isolated_high_veg(i, points, grid, cell_size, xy_radius):
                points[i]['class'] = CLASS_GROUND
                isolated_veg_fixed += 1
        
        if i % 20000 == 0 and i > 0:
            print(f"  Обработано: {i:,}/{len(points):,}")
    
    final = Counter(p['class'] for p in points)
    print(f"\nФинальное распределение:")
    print(f"  Здания (6): {final.get(CLASS_BUILDING, 0):,} (+{final.get(CLASS_BUILDING, 0) - initial.get(CLASS_BUILDING, 0):,})")
    print(f"  Грунт (2): {final.get(CLASS_GROUND, 0):,}")
    print(f"  Высокая раст. (5): {final.get(CLASS_HIGH_VEG, 0):,}")
    
    print(f"\n{'='*50}")
    print(f"Стен конвертировано в здания: {walls_converted:,}")
    print(f"Вертикальный грунт → высокая раст.: {vertical_ground_fixed:,}")
    print(f"Изолированная высокая раст. → грунт: {isolated_veg_fixed:,}")
    
    return points, walls_converted + vertical_ground_fixed + isolated_veg_fixed

def main():
    if len(sys.argv) < 2:
        print("Lasssy V4.1 - Улучшенное сглаживание зданий v3")
        print("-" * 50)
        print("Обнаружение вертикальных стен и полов зданий")
        print("")
        print("Использование: python smooth_buildings_v3.py <input.xyz> [output.xyz]")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else input_file.replace('.xyz', '_walls_fixed.xyz')
    
    print("=" * 50)
    print("  Lasssy V4.1 - Обнаружение стен зданий v3")
    print("=" * 50)
    
    print(f"\nЗагрузка: {input_file}")
    points = load_points(input_file)
    print(f"Всего точек: {len(points):,}")
    
    print(f"\nОбработка...")
    points, changes = smooth_buildings_v3(points)
    
    print(f"\nСохранение: {output_file}")
    save_points(points, output_file)
    print("✓ Готово!")

if __name__ == "__main__":
    main()
