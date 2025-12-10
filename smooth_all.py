#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Lasssy V4.5 - Максимально оптимизированный пайплайн сглаживания

ОПТИМИЗАЦИИ:
- NumPy массивы (вместо списка словарей)
- scipy.spatial.cKDTree (быстрый поиск соседей)
- Numba JIT компиляция (Python → машинный код)
- Параллельная обработка (prange)
- Векторизованные операции

Запуск: python smooth_all.py <input.xyz> [output.xyz]
Зависимости: pip install numpy scipy numba
"""

import sys
import numpy as np
from collections import Counter

# Попытка импорта оптимизаций
try:
    from scipy.spatial import cKDTree
    USE_KDTREE = True
except ImportError:
    USE_KDTREE = False
    print("⚠️ scipy не найден")

try:
    from numba import njit, prange
    USE_NUMBA = True
except ImportError:
    USE_NUMBA = False
    print("⚠️ numba не найден (для дополнительного ускорения: pip install numba)")

# Константы классов
CLASS_GROUND = 2
CLASS_LOW_VEG = 3
CLASS_MED_VEG = 4
CLASS_HIGH_VEG = 5
CLASS_BUILDING = 6
CLASS_NOISE = 7

def load_points_numpy(filepath):
    """Загрузка точек в NumPy массивы"""
    classes = []
    coords = []
    
    with open(filepath, 'r') as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) >= 4:
                classes.append(int(parts[0]))
                coords.append([float(parts[1]), float(parts[2]), float(parts[3])])
    
    return np.array(classes, dtype=np.int32), np.array(coords, dtype=np.float64)

def save_points_numpy(classes, coords, filepath):
    """Сохранение точек из NumPy массивов"""
    with open(filepath, 'w') as f:
        for i in range(len(classes)):
            f.write(f"{classes[i]} {coords[i,0]:.3f} {coords[i,1]:.3f} {coords[i,2]:.3f}\n")

# ============= NUMBA-ОПТИМИЗИРОВАННЫЕ ФУНКЦИИ =============

if USE_NUMBA:
    @njit(parallel=True, cache=True, fastmath=True)
    def process_walls_numba(classes, coords, neighbor_indices, neighbor_counts, max_neighbors):
        """Numba-оптимизированная обработка стен зданий"""
        n_points = len(classes)
        new_classes = classes.copy()
        walls_converted = 0
        vertical_ground_fixed = 0
        
        for i in prange(n_points):
            current_class = classes[i]
            current_z = coords[i, 2]
            n_neighbors = neighbor_counts[i]
            
            if n_neighbors <= 1:
                continue
            
            # Подсчёт статистики соседей
            buildings_above = 0
            buildings_same = 0
            total_above = 0
            min_z = current_z
            
            for j in range(n_neighbors):
                n_idx = neighbor_indices[i, j]
                if n_idx < 0:
                    break
                n_class = classes[n_idx]
                n_z = coords[n_idx, 2]
                z_diff = n_z - current_z
                
                if n_z < min_z:
                    min_z = n_z
                
                if z_diff > 0.5:
                    total_above += 1
                    if n_class == CLASS_BUILDING:
                        buildings_above += 1
                elif abs(z_diff) <= 0.5:
                    if n_class == CLASS_BUILDING:
                        buildings_same += 1
            
            # Растительность → стена здания
            if current_class in (CLASS_LOW_VEG, CLASS_MED_VEG, CLASS_HIGH_VEG):
                if buildings_above > 0 and total_above > 0:
                    if buildings_above / total_above >= 0.3:
                        new_classes[i] = CLASS_BUILDING
                        walls_converted += 1
                        continue
                if buildings_same >= 2:
                    new_classes[i] = CLASS_BUILDING
                    walls_converted += 1
                    continue
            
            # Грунт → вертикальный грунт
            elif current_class == CLASS_GROUND:
                height_above_base = current_z - min_z
                if height_above_base >= 2.0 and total_above >= 5:
                    new_classes[i] = CLASS_HIGH_VEG
                    vertical_ground_fixed += 1
        
        return new_classes, walls_converted, vertical_ground_fixed

    @njit(parallel=True, cache=True, fastmath=True)
    def process_isolated_veg_numba(classes, coords, neighbor_indices, neighbor_counts, max_neighbors):
        """Numba-оптимизированная обработка изолированной растительности"""
        n_points = len(classes)
        new_classes = classes.copy()
        isolated_veg_fixed = 0
        
        for i in prange(n_points):
            if classes[i] != CLASS_HIGH_VEG:
                continue
            
            current_z = coords[i, 2]
            n_neighbors = neighbor_counts[i]
            
            if n_neighbors <= 1:
                continue
            
            low_med_above = 0
            total_above = 0
            same_level_count = 0
            same_level_ground = 0
            
            for j in range(n_neighbors):
                n_idx = neighbor_indices[i, j]
                if n_idx < 0:
                    break
                n_class = classes[n_idx]
                n_z = coords[n_idx, 2]
                z_diff = n_z - current_z
                
                if z_diff > 0.5:
                    total_above += 1
                    if n_class == CLASS_LOW_VEG or n_class == CLASS_MED_VEG:
                        low_med_above += 1
                elif abs(z_diff) <= 0.5:
                    same_level_count += 1
                    if n_class == CLASS_GROUND:
                        same_level_ground += 1
            
            # Низкая/средняя растительность выше = ошибка
            if low_med_above >= 1:
                new_classes[i] = CLASS_GROUND
                isolated_veg_fixed += 1
                continue
            
            # Много точек выше = настоящее дерево
            if total_above >= 3:
                continue
            
            # Окружён грунтом
            if same_level_count >= 2:
                if same_level_ground / same_level_count >= 0.5:
                    new_classes[i] = CLASS_GROUND
                    isolated_veg_fixed += 1
        
        return new_classes, isolated_veg_fixed

    @njit(parallel=True, cache=True, fastmath=True)
    def process_isolated_ground_numba(classes, coords, neighbor_indices, neighbor_counts, max_neighbors):
        """Numba-оптимизированная фильтрация одиночного грунта"""
        n_points = len(classes)
        new_classes = classes.copy()
        isolated_ground_fixed = 0
        
        for i in prange(n_points):
            if classes[i] != CLASS_GROUND:
                continue
            
            current_z = coords[i, 2]
            n_neighbors = neighbor_counts[i]
            same_level_ground = 0
            
            for j in range(n_neighbors):
                n_idx = neighbor_indices[i, j]
                if n_idx < 0:
                    break
                if n_idx == i:
                    continue
                n_class = classes[n_idx]
                n_z = coords[n_idx, 2]
                
                if abs(n_z - current_z) <= 0.5 and n_class == CLASS_GROUND:
                    same_level_ground += 1
            
            if same_level_ground < 3:
                new_classes[i] = CLASS_HIGH_VEG
                isolated_ground_fixed += 1
        
        return new_classes, isolated_ground_fixed

    @njit(parallel=True, cache=True, fastmath=True)
    def process_vegetation_pass_numba(classes, coords, neighbor_indices, neighbor_counts, 
                                       max_neighbors, radius, confidence, min_neighbors):
        """Numba-оптимизированный проход сглаживания растительности"""
        n_points = len(classes)
        new_classes = classes.copy()
        changes = 0
        
        for i in prange(n_points):
            current_class = classes[i]
            if current_class not in (CLASS_LOW_VEG, CLASS_MED_VEG, CLASS_HIGH_VEG):
                continue
            
            n_neighbors = neighbor_counts[i]
            if n_neighbors < min_neighbors:
                continue
            
            current_coord = coords[i]
            
            # Weighted voting
            weight_low = 0.0
            weight_med = 0.0
            weight_high = 0.0
            total_weight = 0.0
            veg_count = 0
            
            for j in range(n_neighbors):
                n_idx = neighbor_indices[i, j]
                if n_idx < 0 or n_idx == i:
                    continue
                n_class = classes[n_idx]
                
                if n_class in (CLASS_LOW_VEG, CLASS_MED_VEG, CLASS_HIGH_VEG):
                    # Вычисляем расстояние и вес
                    dx = coords[n_idx, 0] - current_coord[0]
                    dy = coords[n_idx, 1] - current_coord[1]
                    dz = coords[n_idx, 2] - current_coord[2]
                    dist = np.sqrt(dx*dx + dy*dy + dz*dz)
                    weight = 1.0 - (dist / radius)
                    
                    if weight > 0:
                        if n_class == CLASS_LOW_VEG:
                            weight_low += weight
                        elif n_class == CLASS_MED_VEG:
                            weight_med += weight
                        else:
                            weight_high += weight
                        total_weight += weight
                        veg_count += 1
            
            if veg_count < min_neighbors or total_weight < 1.0:
                continue
            
            # Находим доминирующий класс
            max_weight = weight_low
            dominant_class = CLASS_LOW_VEG
            if weight_med > max_weight:
                max_weight = weight_med
                dominant_class = CLASS_MED_VEG
            if weight_high > max_weight:
                max_weight = weight_high
                dominant_class = CLASS_HIGH_VEG
            
            conf = max_weight / total_weight
            
            if conf >= confidence and dominant_class != current_class:
                new_classes[i] = dominant_class
                changes += 1
        
        return new_classes, changes

def prepare_neighbor_arrays(all_neighbors, max_neighbors=100):
    """Преобразуем список соседей в 2D массив для Numba"""
    n_points = len(all_neighbors)
    neighbor_indices = np.full((n_points, max_neighbors), -1, dtype=np.int32)
    neighbor_counts = np.zeros(n_points, dtype=np.int32)
    
    for i, neighbors in enumerate(all_neighbors):
        n = min(len(neighbors), max_neighbors)
        neighbor_counts[i] = n
        for j in range(n):
            neighbor_indices[i, j] = neighbors[j]
    
    return neighbor_indices, neighbor_counts

# ============= ГЛАВНЫЕ ФУНКЦИИ =============

def smooth_buildings_v3_optimized(classes, coords, xy_radius=1.5):
    """Оптимизированное сглаживание зданий"""
    print("\n" + "="*50)
    print("  ЭТАП 1: Сглаживание зданий v3" + (" (Numba)" if USE_NUMBA else ""))
    print("="*50)
    
    n_points = len(classes)
    initial_buildings = np.sum(classes == CLASS_BUILDING)
    initial_ground = np.sum(classes == CLASS_GROUND)
    print(f"Здания до: {initial_buildings:,}")
    print(f"Грунт до: {initial_ground:,}")
    
    # Строим 2D KD-дерево
    coords_2d = coords[:, :2]
    tree_2d = cKDTree(coords_2d)
    
    print("\nПостроение индексов соседей...")
    all_neighbors = tree_2d.query_ball_point(coords_2d, r=xy_radius, workers=-1)
    
    if USE_NUMBA:
        neighbor_indices, neighbor_counts = prepare_neighbor_arrays(all_neighbors)
        max_neighbors = neighbor_indices.shape[1]
        
        print("Этап 1.1: Стены зданий и вертикальный грунт...")
        classes, walls_converted, vertical_ground_fixed = process_walls_numba(
            classes, coords, neighbor_indices, neighbor_counts, max_neighbors)
        
        print("Этап 1.2: Изолированная высокая растительность...")
        classes, isolated_veg_fixed = process_isolated_veg_numba(
            classes, coords, neighbor_indices, neighbor_counts, max_neighbors)
        
        print("Этап 1.3: Фильтрация одиночных точек грунта...")
        classes, isolated_ground_fixed = process_isolated_ground_numba(
            classes, coords, neighbor_indices, neighbor_counts, max_neighbors)
    else:
        # Fallback без Numba (медленнее)
        walls_converted = 0
        vertical_ground_fixed = 0
        isolated_veg_fixed = 0
        isolated_ground_fixed = 0
        
        print("\nЭтап 1.1: Стены зданий и вертикальный грунт...")
        for i in range(n_points):
            neighbors = all_neighbors[i]
            if len(neighbors) <= 1:
                continue
            
            neighbor_classes = classes[neighbors]
            neighbor_z = coords[neighbors, 2]
            current_z = coords[i, 2]
            
            if classes[i] in (CLASS_LOW_VEG, CLASS_MED_VEG, CLASS_HIGH_VEG):
                above_mask = neighbor_z > current_z + 0.5
                buildings_above = np.sum((neighbor_classes == CLASS_BUILDING) & above_mask)
                total_above = np.sum(above_mask)
                same_level_mask = np.abs(neighbor_z - current_z) <= 0.5
                buildings_same = np.sum((neighbor_classes == CLASS_BUILDING) & same_level_mask)
                
                if buildings_above > 0 and total_above > 0 and buildings_above / total_above >= 0.3:
                    classes[i] = CLASS_BUILDING
                    walls_converted += 1
                    continue
                if buildings_same >= 2:
                    classes[i] = CLASS_BUILDING
                    walls_converted += 1
                    continue
            
            elif classes[i] == CLASS_GROUND:
                min_z = np.min(neighbor_z)
                if current_z - min_z >= 2.0:
                    above_mask = neighbor_z > current_z + 0.5
                    if np.sum(above_mask) >= 5:
                        classes[i] = CLASS_HIGH_VEG
                        vertical_ground_fixed += 1
        
        print("\nЭтап 1.2: Изолированная высокая растительность...")
        for i in range(n_points):
            if classes[i] != CLASS_HIGH_VEG:
                continue
            neighbors = all_neighbors[i]
            if len(neighbors) <= 1:
                continue
            
            neighbor_classes = classes[neighbors]
            neighbor_z = coords[neighbors, 2]
            current_z = coords[i, 2]
            
            above_mask = neighbor_z > current_z + 0.5
            low_med_above = np.sum(((neighbor_classes == CLASS_LOW_VEG) | 
                                    (neighbor_classes == CLASS_MED_VEG)) & above_mask)
            if low_med_above >= 1:
                classes[i] = CLASS_GROUND
                isolated_veg_fixed += 1
                continue
            
            if np.sum(above_mask) >= 3:
                continue
            
            same_level_mask = np.abs(neighbor_z - current_z) <= 0.5
            same_level_classes = neighbor_classes[same_level_mask]
            if len(same_level_classes) >= 2:
                if np.sum(same_level_classes == CLASS_GROUND) / len(same_level_classes) >= 0.5:
                    classes[i] = CLASS_GROUND
                    isolated_veg_fixed += 1
        
        print("\nЭтап 1.3: Фильтрация одиночных точек грунта...")
        for i in range(n_points):
            if classes[i] != CLASS_GROUND:
                continue
            neighbors = all_neighbors[i]
            neighbor_classes = classes[neighbors]
            neighbor_z = coords[neighbors, 2]
            current_z = coords[i, 2]
            same_level_mask = np.abs(neighbor_z - current_z) <= 0.5
            same_level_ground = np.sum((neighbor_classes == CLASS_GROUND) & same_level_mask) - 1
            if same_level_ground < 3:
                classes[i] = CLASS_HIGH_VEG
                isolated_ground_fixed += 1
    
    final_buildings = np.sum(classes == CLASS_BUILDING)
    final_ground = np.sum(classes == CLASS_GROUND)
    print(f"\nЗдания после: {final_buildings:,} (+{walls_converted})")
    print(f"Грунт после: {final_ground:,}")
    print(f"Стен→зданий: {walls_converted}, Верт.грунт→раст: {vertical_ground_fixed}")
    print(f"Изол.раст→грунт: {isolated_veg_fixed}, Изол.грунт→раст: {isolated_ground_fixed}")
    
    return classes, walls_converted + vertical_ground_fixed + isolated_veg_fixed + isolated_ground_fixed

def smooth_vegetation_v2_optimized(classes, coords, radius=2.0, passes=3, confidence=0.55, min_neighbors=4):
    """Оптимизированное сглаживание растительности"""
    print("\n" + "="*50)
    print("  ЭТАП 2: Сглаживание растительности v2" + (" (Numba)" if USE_NUMBA else ""))
    print("="*50)
    
    veg_count = {3: np.sum(classes == 3), 4: np.sum(classes == 4), 5: np.sum(classes == 5)}
    print(f"До: низкая={veg_count[3]:,}, средняя={veg_count[4]:,}, высокая={veg_count[5]:,}")
    
    # Строим 3D KD-дерево
    tree_3d = cKDTree(coords)
    
    print("Построение индексов соседей...")
    all_neighbors = tree_3d.query_ball_point(coords, r=radius, workers=-1)
    
    total_changes = 0
    
    if USE_NUMBA:
        neighbor_indices, neighbor_counts = prepare_neighbor_arrays(all_neighbors)
        max_neighbors = neighbor_indices.shape[1]
        
        for pass_num in range(1, passes + 1):
            classes, changes = process_vegetation_pass_numba(
                classes, coords, neighbor_indices, neighbor_counts,
                max_neighbors, radius, confidence, min_neighbors)
            total_changes += changes
            print(f"  Проход {pass_num}: {changes:,} изменений")
            if changes == 0:
                break
    else:
        # Fallback без Numba
        for pass_num in range(1, passes + 1):
            changes = 0
            new_classes = classes.copy()
            
            veg_indices = np.where(np.isin(classes, [CLASS_LOW_VEG, CLASS_MED_VEG, CLASS_HIGH_VEG]))[0]
            
            for i in veg_indices:
                neighbors = all_neighbors[i]
                if len(neighbors) < min_neighbors:
                    continue
                
                neighbor_classes = classes[neighbors]
                neighbor_coords = coords[neighbors]
                current_coord = coords[i]
                
                weighted_votes = {CLASS_LOW_VEG: 0.0, CLASS_MED_VEG: 0.0, CLASS_HIGH_VEG: 0.0}
                total_weight = 0.0
                veg_count_local = 0
                
                for j, n_idx in enumerate(neighbors):
                    if n_idx == i:
                        continue
                    n_class = neighbor_classes[j]
                    if n_class in (CLASS_LOW_VEG, CLASS_MED_VEG, CLASS_HIGH_VEG):
                        dist = np.linalg.norm(neighbor_coords[j] - current_coord)
                        weight = 1.0 - (dist / radius)
                        if weight > 0:
                            weighted_votes[n_class] += weight
                            total_weight += weight
                            veg_count_local += 1
                
                if veg_count_local < min_neighbors or total_weight < 1.0:
                    continue
                
                dominant_class = max(weighted_votes, key=weighted_votes.get)
                conf = weighted_votes[dominant_class] / total_weight
                
                if conf >= confidence and dominant_class != classes[i]:
                    new_classes[i] = dominant_class
                    changes += 1
            
            classes = new_classes
            total_changes += changes
            print(f"  Проход {pass_num}: {changes:,} изменений")
            if changes == 0:
                break
    
    veg_final = {3: np.sum(classes == 3), 4: np.sum(classes == 4), 5: np.sum(classes == 5)}
    print(f"После: низкая={veg_final[3]:,}, средняя={veg_final[4]:,}, высокая={veg_final[5]:,}")
    print(f"Всего изменений: {total_changes:,}")
    
    return classes, total_changes

def smooth_all(input_file, output_file):
    """Полный оптимизированный пайплайн"""
    print("="*50)
    print("  Lasssy V4.5 - Максимально оптимизированное сглаживание")
    print("="*50)
    
    if not USE_KDTREE:
        print("\n❌ scipy не установлен! pip install scipy")
        return
    
    if USE_NUMBA:
        print("✓ Numba JIT активен (максимальная скорость)")
    else:
        print("⚠️ Numba не установлен (pip install numba для 10x ускорения)")
    
    print(f"\nЗагрузка: {input_file}")
    classes, coords = load_points_numpy(input_file)
    print(f"Всего точек: {len(classes):,}")
    
    classes, building_changes = smooth_buildings_v3_optimized(classes, coords)
    classes, veg_changes = smooth_vegetation_v2_optimized(classes, coords)
    
    print("\n" + "="*50)
    print(f"Сохранение: {output_file}")
    save_points_numpy(classes, coords, output_file)
    
    print(f"\n✓ Готово! Зданий: {building_changes} изменений, Растений: {veg_changes} изменений")
    
    return building_changes, veg_changes

def main():
    if len(sys.argv) < 2:
        print("Lasssy V4.5 - Максимально оптимизированный пайплайн сглаживания")
        print("-" * 50)
        print("Использование: python smooth_all.py <input.xyz> [output.xyz]")
        print("")
        print("Зависимости:")
        print("  pip install numpy scipy       # Обязательно")
        print("  pip install numba             # Для 10x ускорения")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else input_file.replace('.xyz', '_smoothed.xyz')
    
    smooth_all(input_file, output_file)

if __name__ == "__main__":
    main()
