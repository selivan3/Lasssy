#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Lasssy V4 - Семантическое сглаживание классов растительности
Если большинство соседних точек имеют один класс растительности (3,4,5),
то текущая точка принимает этот класс.
"""

import sys
import os
from collections import Counter
import math

def load_points(filepath):
    """Загрузка точек из XYZ файла (class x y z)"""
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
    """Сохранение точек в XYZ файл"""
    with open(filepath, 'w') as f:
        for p in points:
            f.write(f"{p['class']} {p['x']:.3f} {p['y']:.3f} {p['z']:.3f}\n")

def build_grid(points, cell_size):
    """Построение пространственной сетки для быстрого поиска соседей"""
    grid = {}
    for i, p in enumerate(points):
        key = (int(p['x'] / cell_size), int(p['y'] / cell_size), int(p['z'] / cell_size))
        if key not in grid:
            grid[key] = []
        grid[key].append(i)
    return grid

def get_neighbors(idx, points, grid, cell_size, radius):
    """Получение индексов соседних точек в радиусе"""
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
                            neighbors.append(j)
    return neighbors

def smooth_vegetation(points, radius=1.5, min_neighbors=3):
    """
    Семантическое сглаживание классов растительности.
    Если большинство соседей имеют определённый класс растительности,
    точка принимает этот класс.
    """
    veg_classes = {3, 4, 5}  # Классы растительности
    cell_size = radius * 2
    
    print(f"Построение сетки (размер ячейки: {cell_size})...")
    grid = build_grid(points, cell_size)
    
    # Подсчёт до сглаживания
    before_counts = Counter(p['class'] for p in points)
    print(f"До сглаживания: 3={before_counts.get(3,0)}, 4={before_counts.get(4,0)}, 5={before_counts.get(5,0)}")
    
    changes = 0
    new_classes = [p['class'] for p in points]
    
    print(f"Обработка {len(points)} точек...")
    for i, p in enumerate(points):
        # Сглаживаем только точки растительности
        if p['class'] not in veg_classes:
            continue
        
        neighbors = get_neighbors(i, points, grid, cell_size, radius)
        
        if len(neighbors) < min_neighbors:
            continue
        
        # Считаем классы соседей (только растительность)
        veg_neighbors = [points[j]['class'] for j in neighbors if points[j]['class'] in veg_classes]
        
        if len(veg_neighbors) < min_neighbors:
            continue
        
        # Определяем доминирующий класс
        class_counts = Counter(veg_neighbors)
        most_common = class_counts.most_common(1)[0]
        dominant_class = most_common[0]
        dominant_count = most_common[1]
        
        # Если большинство (>50%) соседей имеют один класс
        if dominant_count > len(veg_neighbors) / 2 and dominant_class != p['class']:
            new_classes[i] = dominant_class
            changes += 1
        
        if i % 50000 == 0 and i > 0:
            print(f"  Обработано: {i}/{len(points)}, изменений: {changes}")
    
    # Применяем изменения
    for i, new_cls in enumerate(new_classes):
        points[i]['class'] = new_cls
    
    # Подсчёт после сглаживания
    after_counts = Counter(p['class'] for p in points)
    print(f"После сглаживания: 3={after_counts.get(3,0)}, 4={after_counts.get(4,0)}, 5={after_counts.get(5,0)}")
    print(f"Изменено точек: {changes}")
    
    return points

def main():
    if len(sys.argv) < 2:
        print("Использование: python smooth_vegetation.py <input.xyz> [output.xyz] [radius]")
        print("  radius: радиус поиска соседей (по умолчанию 1.5)")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else input_file.replace('.xyz', '_smoothed.xyz')
    radius = float(sys.argv[3]) if len(sys.argv) > 3 else 1.5
    
    print(f"Загрузка: {input_file}")
    points = load_points(input_file)
    print(f"Загружено точек: {len(points)}")
    
    print(f"\nСглаживание (радиус={radius})...")
    points = smooth_vegetation(points, radius=radius)
    
    print(f"\nСохранение: {output_file}")
    save_points(points, output_file)
    print("Готово!")

if __name__ == "__main__":
    main()
