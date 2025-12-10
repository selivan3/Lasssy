#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Lasssy V4.2 - Полный пайплайн сглаживания

Порядок:
1. Сглаживание зданий v3 (стены, вертикальный грунт, изолированная растительность)
2. Сглаживание растительности v2 (weighted voting)

Запуск: python smooth_all.py <input.xyz> [output.xyz]
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

# ============= СГЛАЖИВАНИЕ ЗДАНИЙ V3 =============

def build_grid_2d(points, cell_size):
    grid = defaultdict(list)
    for i, p in enumerate(points):
        key = (int(p['x'] / cell_size), int(p['y'] / cell_size))
        grid[key].append(i)
    return grid

def get_vertical_column(x, y, points, grid, cell_size, xy_radius):
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
    p = points[idx]
    column = get_vertical_column(p['x'], p['y'], points, grid, cell_size, xy_radius)
    
    buildings_above = []
    all_above = []
    buildings_same = []
    
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
        elif abs(z_diff) <= z_tolerance:
            if q['class'] == CLASS_BUILDING:
                buildings_same.append(j)
    
    return {
        'buildings_above': len(buildings_above),
        'buildings_same': len(buildings_same),
        'total_above': len(all_above)
    }

def is_vertical_wall(idx, points, grid, cell_size, xy_radius):
    p = points[idx]
    if p['class'] == CLASS_BUILDING:
        return False
    
    analysis = analyze_vertical_structure(idx, points, grid, cell_size, xy_radius)
    
    if analysis['buildings_above'] == 0:
        return False
    
    if analysis['total_above'] > 0:
        ratio = analysis['buildings_above'] / analysis['total_above']
        if ratio >= 0.3:
            return True
    
    if analysis['buildings_same'] >= 2:
        return True
    
    return False

def is_vertical_ground(idx, points, grid, cell_size, xy_radius, min_height=2.0, min_points_above=5):
    p = points[idx]
    if p['class'] != CLASS_GROUND:
        return False
    
    column = get_vertical_column(p['x'], p['y'], points, grid, cell_size, xy_radius)
    if column:
        min_z = min(points[j]['z'] for j in column)
        if p['z'] - min_z < min_height:
            return False
    
    analysis = analyze_vertical_structure(idx, points, grid, cell_size, xy_radius)
    if analysis['total_above'] >= min_points_above:
        return True
    
    return False

def is_isolated_high_veg(idx, points, grid, cell_size, xy_radius, min_ground_ratio=0.5):
    p = points[idx]
    if p['class'] != CLASS_HIGH_VEG:
        return False
    
    column = get_vertical_column(p['x'], p['y'], points, grid, cell_size, xy_radius)
    
    same_level = []
    above = []
    low_med_above = 0
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
            if q['class'] in {CLASS_LOW_VEG, CLASS_MED_VEG}:
                low_med_above += 1
    
    # Высокая растительность под низкой/средней = грунт
    if low_med_above >= 1:
        return True
    
    if len(above) >= 3:
        return False
    
    if len(same_level) < 2:
        return False
    
    ground_neighbors = sum(1 for j in same_level if points[j]['class'] == CLASS_GROUND)
    if len(same_level) > 0 and ground_neighbors / len(same_level) >= min_ground_ratio:
        return True
    
    return False

def smooth_buildings_v3(points, xy_radius=1.5):
    """Сглаживание зданий v3 - стены, вертикальный грунт, изолированная растительность"""
    print("\n" + "="*50)
    print("  ЭТАП 1: Сглаживание зданий v3")
    print("="*50)
    
    cell_size = xy_radius * 2
    grid = build_grid_2d(points, cell_size)
    
    initial = Counter(p['class'] for p in points)
    print(f"Здания до: {initial.get(CLASS_BUILDING, 0):,}")
    print(f"Грунт до: {initial.get(CLASS_GROUND, 0):,}")
    
    walls_converted = 0
    vertical_ground_fixed = 0
    isolated_veg_fixed = 0
    
    print("\nЭтап 1.1: Стены зданий и вертикальный грунт...")
    for i, p in enumerate(points):
        if p['class'] in VEG_CLASSES:
            if is_vertical_wall(i, points, grid, cell_size, xy_radius):
                points[i]['class'] = CLASS_BUILDING
                walls_converted += 1
        elif p['class'] == CLASS_GROUND:
            if is_vertical_ground(i, points, grid, cell_size, xy_radius):
                points[i]['class'] = CLASS_HIGH_VEG
                vertical_ground_fixed += 1
    
    print("\nЭтап 1.2: Изолированная высокая растительность...")
    for i, p in enumerate(points):
        if p['class'] == CLASS_HIGH_VEG:
            if is_isolated_high_veg(i, points, grid, cell_size, xy_radius):
                points[i]['class'] = CLASS_GROUND
                isolated_veg_fixed += 1
    
    # Этап 1.3: Фильтрация одиночных точек грунта (менее 3 соседей грунта)
    print("\nЭтап 1.3: Фильтрация одиночных точек грунта...")
    isolated_ground_fixed = 0
    for i, p in enumerate(points):
        if p['class'] == CLASS_GROUND:
            column = get_vertical_column(p['x'], p['y'], points, grid, cell_size, xy_radius)
            # Считаем соседей-грунт на том же уровне
            same_level_ground = 0
            for j in column:
                if j == i:
                    continue
                q = points[j]
                if abs(q['z'] - p['z']) <= 0.5 and q['class'] == CLASS_GROUND:
                    same_level_ground += 1
            # Если менее 3 соседей-грунт - это изолированная точка
            if same_level_ground < 3:
                points[i]['class'] = CLASS_HIGH_VEG
                isolated_ground_fixed += 1
    
    final = Counter(p['class'] for p in points)
    print(f"\nЗдания после: {final.get(CLASS_BUILDING, 0):,} (+{walls_converted})")
    print(f"Грунт после: {final.get(CLASS_GROUND, 0):,}")
    print(f"Стен→зданий: {walls_converted}, Верт.грунт→раст: {vertical_ground_fixed}")
    print(f"Изол.раст→грунт: {isolated_veg_fixed}, Изол.грунт→раст: {isolated_ground_fixed}")
    
    return points, walls_converted + vertical_ground_fixed + isolated_veg_fixed + isolated_ground_fixed

# ============= СГЛАЖИВАНИЕ РАСТИТЕЛЬНОСТИ V2 =============

def build_grid_3d(points, cell_size):
    grid = defaultdict(list)
    for i, p in enumerate(points):
        key = (int(p['x'] / cell_size), int(p['y'] / cell_size), int(p['z'] / cell_size))
        grid[key].append(i)
    return grid

def get_neighbors_weighted(idx, points, grid, cell_size, radius):
    p = points[idx]
    gx = int(p['x'] / cell_size)
    gy = int(p['y'] / cell_size)
    gz = int(p['z'] / cell_size)
    
    neighbors = []
    radius_sq = radius * radius
    
    for dx in range(-1, 2):
        for dy in range(-1, 2):
            for dz in range(-1, 2):
                key = (gx + dx, gy + dy, gz + dz)
                if key in grid:
                    for j in grid[key]:
                        if j == idx:
                            continue
                        q = points[j]
                        dist_sq = (p['x'] - q['x'])**2 + (p['y'] - q['y'])**2 + (p['z'] - q['z'])**2
                        if dist_sq <= radius_sq:
                            dist = math.sqrt(dist_sq)
                            weight = 1.0 - (dist / radius)
                            neighbors.append((j, weight))
    return neighbors

def smooth_vegetation_v2(points, radius=2.0, passes=3, confidence=0.55, min_neighbors=4):
    """Сглаживание растительности v2 - weighted voting"""
    print("\n" + "="*50)
    print("  ЭТАП 2: Сглаживание растительности v2")
    print("="*50)
    
    cell_size = radius * 1.5
    grid = build_grid_3d(points, cell_size)
    
    veg_count = Counter(p['class'] for p in points if p['class'] in VEG_CLASSES)
    print(f"До: низкая={veg_count.get(3,0):,}, средняя={veg_count.get(4,0):,}, высокая={veg_count.get(5,0):,}")
    
    total_changes = 0
    
    for pass_num in range(1, passes + 1):
        changes = 0
        new_classes = [p['class'] for p in points]
        
        for i, p in enumerate(points):
            if p['class'] not in VEG_CLASSES:
                continue
            
            neighbors = get_neighbors_weighted(i, points, grid, cell_size, radius)
            
            weighted_votes = defaultdict(float)
            total_weight = 0.0
            veg_count_local = 0
            
            for j, weight in neighbors:
                neighbor_class = points[j]['class']
                if neighbor_class in VEG_CLASSES:
                    weighted_votes[neighbor_class] += weight
                    total_weight += weight
                    veg_count_local += 1
            
            if veg_count_local < min_neighbors or total_weight < 1.0:
                continue
            
            sorted_votes = sorted(weighted_votes.items(), key=lambda x: -x[1])
            if not sorted_votes:
                continue
                
            dominant_class = sorted_votes[0][0]
            dominant_weight = sorted_votes[0][1]
            conf = dominant_weight / total_weight
            
            if conf >= confidence and dominant_class != p['class']:
                new_classes[i] = dominant_class
                changes += 1
        
        for i, new_cls in enumerate(new_classes):
            points[i]['class'] = new_cls
        
        total_changes += changes
        print(f"  Проход {pass_num}: {changes:,} изменений")
        
        if changes == 0:
            break
    
    veg_final = Counter(p['class'] for p in points if p['class'] in VEG_CLASSES)
    print(f"После: низкая={veg_final.get(3,0):,}, средняя={veg_final.get(4,0):,}, высокая={veg_final.get(5,0):,}")
    print(f"Всего изменений: {total_changes:,}")
    
    return points, total_changes

# ============= ГЛАВНАЯ ФУНКЦИЯ =============

def smooth_all(input_file, output_file):
    """Полный пайплайн сглаживания"""
    print("="*50)
    print("  Lasssy V4.2 - Полное сглаживание")
    print("="*50)
    
    print(f"\nЗагрузка: {input_file}")
    points = load_points(input_file)
    print(f"Всего точек: {len(points):,}")
    
    # Этап 1: Здания v3
    points, building_changes = smooth_buildings_v3(points)
    
    # Этап 2: Растительность v2
    points, veg_changes = smooth_vegetation_v2(points)
    
    # Сохранение
    print("\n" + "="*50)
    print(f"Сохранение: {output_file}")
    save_points(points, output_file)
    
    print(f"\n✓ Готово! Зданий: {building_changes} изменений, Растений: {veg_changes} изменений")
    
    return building_changes, veg_changes

def main():
    if len(sys.argv) < 2:
        print("Lasssy V4.2 - Полный пайплайн сглаживания")
        print("-" * 50)
        print("Использование: python smooth_all.py <input.xyz> [output.xyz]")
        print("")
        print("Порядок обработки:")
        print("  1. Сглаживание зданий v3 (стены, верт. грунт, изол. растительность)")
        print("  2. Сглаживание растительности v2 (weighted voting)")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else input_file.replace('.xyz', '_smoothed.xyz')
    
    smooth_all(input_file, output_file)

if __name__ == "__main__":
    main()
