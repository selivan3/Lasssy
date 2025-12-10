#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Lasssy V4 - Улучшенное семантическое сглаживание растительности

Алгоритм:
1. Анализирует локальный контекст каждой точки растительности
2. Если большинство соседей имеют один класс - точка принимает этот класс
3. Учитывает вес по расстоянию (ближние соседи важнее)
4. Использует порог уверенности (не меняем если нет явного большинства)
5. Несколько проходов для лучшего растечения контекста
6. Защита от "пятнистости" - требуем минимум N соседей

Ключевое правило: Класс растительности распространяется на соседние точки
растительности, если этот класс доминирует в окрестности.
"""

import sys
import os
from collections import Counter, defaultdict
import math

# Константы
VEG_CLASSES = {3, 4, 5}  # Низкая, средняя, высокая
VEG_NAMES = {3: 'низкая', 4: 'средняя', 5: 'высокая'}

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
                points.append({'class': cls, 'x': x, 'y': y, 'z': z, 'original_class': cls})
    return points

def save_points(points, filepath):
    """Сохранение точек в XYZ файл"""
    with open(filepath, 'w') as f:
        for p in points:
            f.write(f"{p['class']} {p['x']:.3f} {p['y']:.3f} {p['z']:.3f}\n")

def build_grid(points, cell_size):
    """Построение пространственной сетки"""
    grid = defaultdict(list)
    for i, p in enumerate(points):
        key = (int(p['x'] / cell_size), int(p['y'] / cell_size), int(p['z'] / cell_size))
        grid[key].append(i)
    return grid

def get_neighbors_weighted(idx, points, grid, cell_size, radius):
    """
    Получение соседей с весами по расстоянию.
    Возвращает список (индекс, вес), где вес = 1 - (dist/radius)
    """
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
                            # Вес: ближе = больше влияние (1.0 для dist=0, 0.0 для dist=radius)
                            weight = 1.0 - (dist / radius)
                            neighbors.append((j, weight))
    return neighbors

def analyze_neighborhood(idx, points, neighbors, current_class):
    """
    Анализирует окрестность и возвращает:
    - dominant_class: доминирующий класс (или None если нет явного)
    - confidence: уверенность (0.0 - 1.0)
    - вегетативные соседи
    """
    if not neighbors:
        return None, 0.0, 0
    
    # Считаем взвешенные голоса только для растительности
    weighted_votes = defaultdict(float)
    veg_count = 0
    total_weight = 0.0
    
    for j, weight in neighbors:
        neighbor_class = points[j]['class']
        if neighbor_class in VEG_CLASSES:
            weighted_votes[neighbor_class] += weight
            total_weight += weight
            veg_count += 1
    
    if veg_count < 3 or total_weight < 1.0:
        return None, 0.0, veg_count
    
    # Находим доминирующий класс
    if not weighted_votes:
        return None, 0.0, veg_count
    
    sorted_votes = sorted(weighted_votes.items(), key=lambda x: -x[1])
    dominant_class = sorted_votes[0][0]
    dominant_weight = sorted_votes[0][1]
    
    # Уверенность = доля голосов доминирующего класса
    confidence = dominant_weight / total_weight if total_weight > 0 else 0.0
    
    return dominant_class, confidence, veg_count

def smooth_pass(points, grid, cell_size, radius, confidence_threshold=0.55, min_neighbors=4):
    """
    Один проход сглаживания.
    Возвращает новые классы и количество изменений.
    """
    new_classes = [p['class'] for p in points]
    changes = 0
    upgrades = 0  # низкая → средняя/высокая
    downgrades = 0  # высокая → средняя/низкая
    
    for i, p in enumerate(points):
        # Обрабатываем только растительность
        if p['class'] not in VEG_CLASSES:
            continue
        
        neighbors = get_neighbors_weighted(i, points, grid, cell_size, radius)
        dominant_class, confidence, veg_count = analyze_neighborhood(i, points, neighbors, p['class'])
        
        # Требуем достаточно соседей и высокую уверенность
        if dominant_class is None or veg_count < min_neighbors:
            continue
        
        if confidence < confidence_threshold:
            continue
        
        # Меняем класс только если он отличается
        if dominant_class != p['class']:
            new_classes[i] = dominant_class
            changes += 1
            
            # Статистика направления изменений
            if dominant_class > p['class']:
                upgrades += 1
            else:
                downgrades += 1
    
    # Применяем изменения
    for i, new_cls in enumerate(new_classes):
        points[i]['class'] = new_cls
    
    return changes, upgrades, downgrades

def smart_smooth_vegetation(points, radius=2.0, passes=3, confidence=0.55, min_neighbors=4):
    """
    Интеллектуальное сглаживание растительности.
    
    Параметры:
    - radius: радиус поиска соседей (метры)
    - passes: количество проходов
    - confidence: порог уверенности (0.5 = 50% соседей должны иметь один класс)
    - min_neighbors: минимум соседей для принятия решения
    """
    cell_size = radius * 1.5
    
    print(f"Параметры: радиус={radius}м, проходы={passes}, уверенность={confidence*100:.0f}%, мин.соседей={min_neighbors}")
    print(f"Построение сетки...")
    grid = build_grid(points, cell_size)
    
    # Начальная статистика
    veg_count = Counter(p['class'] for p in points if p['class'] in VEG_CLASSES)
    print(f"\nНачальное распределение:")
    for cls in sorted(VEG_CLASSES):
        print(f"  Класс {cls} ({VEG_NAMES[cls]}): {veg_count.get(cls, 0):,}")
    
    total_changes = 0
    total_upgrades = 0
    total_downgrades = 0
    
    for pass_num in range(1, passes + 1):
        changes, upgrades, downgrades = smooth_pass(
            points, grid, cell_size, radius, confidence, min_neighbors
        )
        total_changes += changes
        total_upgrades += upgrades
        total_downgrades += downgrades
        
        print(f"\nПроход {pass_num}: {changes:,} изменений (↑{upgrades:,} ↓{downgrades:,})")
        
        if changes == 0:
            print(f"  Сходимость достигнута, прерывание.")
            break
        
        # Перестраиваем grid если много изменений (классы изменились)
        # В нашем случае не нужно, т.к. grid по координатам
    
    # Финальная статистика
    veg_count_final = Counter(p['class'] for p in points if p['class'] in VEG_CLASSES)
    print(f"\n{'='*50}")
    print(f"ИТОГО изменений: {total_changes:,} (↑{total_upgrades:,} ↓{total_downgrades:,})")
    print(f"\nФинальное распределение:")
    for cls in sorted(VEG_CLASSES):
        before = veg_count.get(cls, 0)
        after = veg_count_final.get(cls, 0)
        diff = after - before
        sign = '+' if diff >= 0 else ''
        print(f"  Класс {cls} ({VEG_NAMES[cls]}): {after:,} ({sign}{diff:,})")
    
    return points

def main():
    if len(sys.argv) < 2:
        print("Lasssy V4 - Умное сглаживание растительности")
        print("-" * 45)
        print("Использование:")
        print("  python smooth_vegetation_v2.py <input.xyz> [output.xyz] [опции]")
        print("")
        print("Опции:")
        print("  --radius=N     Радиус поиска соседей в метрах (по умолчанию 2.0)")
        print("  --passes=N     Количество проходов (по умолчанию 3)")
        print("  --confidence=N Порог уверенности 0.0-1.0 (по умолчанию 0.55)")
        print("  --neighbors=N  Минимум соседей (по умолчанию 4)")
        print("")
        print("Примеры:")
        print("  python smooth_vegetation_v2.py output/Test_01_classified.xyz")
        print("  python smooth_vegetation_v2.py input.xyz output.xyz --radius=2.5 --passes=5")
        sys.exit(1)
    
    # Парсинг аргументов
    input_file = sys.argv[1]
    output_file = None
    radius = 2.0
    passes = 3
    confidence = 0.55
    min_neighbors = 4
    
    for arg in sys.argv[2:]:
        if arg.startswith('--radius='):
            radius = float(arg.split('=')[1])
        elif arg.startswith('--passes='):
            passes = int(arg.split('=')[1])
        elif arg.startswith('--confidence='):
            confidence = float(arg.split('=')[1])
        elif arg.startswith('--neighbors='):
            min_neighbors = int(arg.split('=')[1])
        elif not arg.startswith('--'):
            output_file = arg
    
    if output_file is None:
        output_file = input_file.replace('.xyz', '_smart_smoothed.xyz')
    
    print("=" * 50)
    print("  Lasssy V4 - Умное сглаживание растительности")
    print("=" * 50)
    
    print(f"\nЗагрузка: {input_file}")
    points = load_points(input_file)
    print(f"Всего точек: {len(points):,}")
    
    print(f"\nОбработка...")
    points = smart_smooth_vegetation(points, radius, passes, confidence, min_neighbors)
    
    print(f"\nСохранение: {output_file}")
    save_points(points, output_file)
    print("✓ Готово!")

if __name__ == "__main__":
    main()
