#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Программа для поиска и удаления дубликатов фотографий в заданной папке.
Дубликаты определяются по совпадению содержимого файлов (хэш SHA-256).
"""

import os
import argparse
import hashlib
from collections import defaultdict
from send2trash import send2trash  # для безопасного удаления через корзину

# Расширения файлов, которые считаются изображениями
IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp', '.ico'}


def is_image_file(filename):
    """Проверяет, является ли файл изображением по расширению."""
    ext = os.path.splitext(filename)[1].lower()
    return ext in IMAGE_EXTENSIONS


def get_image_files(folder, recursive=False):
    """
    Возвращает список путей ко всем файлам изображений в папке folder.
    Если recursive=True, обходит подпапки рекурсивно.
    """
    image_files = []
    if recursive:
        for root, dirs, files in os.walk(folder):
            for file in files:
                if is_image_file(file):
                    image_files.append(os.path.join(root, file))
    else:
        for file in os.listdir(folder):
            full_path = os.path.join(folder, file)
            if os.path.isfile(full_path) and is_image_file(file):
                image_files.append(full_path)
    return image_files


def compute_file_hash(filepath, blocksize=65536):
    """
    Вычисляет SHA-256 хэш содержимого файла.
    Читает файл блоками для экономии памяти.
    """
    hasher = hashlib.sha256()
    with open(filepath, 'rb') as f:
        buf = f.read(blocksize)
        while buf:
            hasher.update(buf)
            buf = f.read(blocksize)
    return hasher.hexdigest()


def find_duplicates(file_list):
    """
    Группирует файлы по их хэшу.
    Возвращает словарь {hash: [file1, file2, ...]},
    где значение содержит только списки с длиной > 1 (дубликаты).
    """
    hash_map = defaultdict(list)
    for filepath in file_list:
        try:
            file_hash = compute_file_hash(filepath)
            hash_map[file_hash].append(filepath)
        except (IOError, OSError) as e:
            print(f"Ошибка при обработке файла {filepath}: {e}")
    # Оставляем только группы с дубликатами
    return {h: paths for h, paths in hash_map.items() if len(paths) > 1}


def choose_file_to_keep(file_list, strategy='first'):
    """
    Выбирает файл, который нужно оставить, из списка дубликатов.
    Стратегии:
    - 'first'  : первый в списке (как найден)
    - 'last'   : последний в списке
    - 'newest' : самый новый по времени модификации
    - 'oldest' : самый старый по времени модификации
    """
    if strategy == 'first':
        return file_list[0]
    elif strategy == 'last':
        return file_list[-1]
    elif strategy == 'newest':
        return max(file_list, key=lambda p: os.path.getmtime(p))
    elif strategy == 'oldest':
        return min(file_list, key=lambda p: os.path.getmtime(p))
    else:
        raise ValueError(f"Неизвестная стратегия: {strategy}")


def delete_duplicates(duplicate_groups, keep_strategy='first', dry_run=False, use_trash=False):
    """
    Удаляет дубликаты, оставляя один файл на группу согласно стратегии.
    Если dry_run=True, только выводит информацию, не удаляя.
    Если use_trash=True, перемещает в корзину вместо полного удаления.
    Возвращает количество удалённых файлов.
    """
    deleted_count = 0
    for file_hash, paths in duplicate_groups.items():
        print(f"\nНайдена группа дубликатов (хэш: {file_hash}):")
        for p in paths:
            print(f"  {p}")
        keep = choose_file_to_keep(paths, keep_strategy)
        print(f"  Оставляем: {keep}")
        for filepath in paths:
            if filepath != keep:
                if dry_run:
                    print(f"  [dry-run] Будет удалён: {filepath}")
                else:
                    try:
                        if use_trash:
                            send2trash(filepath)
                            print(f"  Перемещён в корзину: {filepath}")
                        else:
                            os.remove(filepath)
                            print(f"  Удалён: {filepath}")
                        deleted_count += 1
                    except (OSError, PermissionError) as e:
                        print(f"  Ошибка удаления {filepath}: {e}")
    return deleted_count


def main():
    parser = argparse.ArgumentParser(
        description="Поиск и удаление дубликатов фотографий в папке."
    )
    parser.add_argument('folder', help="Путь к папке для сканирования")
    parser.add_argument('-r', '--recursive', action='store_true',
                        help="Рекурсивно обходить подпапки")
    parser.add_argument('-n', '--dry-run', action='store_true',
                        help="Только показать, что будет удалено (без реального удаления)")
    parser.add_argument('--keep', choices=['first', 'last', 'newest', 'oldest'],
                        default='last', help="Стратегия выбора файла для сохранения (по умолчанию last)")
    parser.add_argument('-t', '--use-trash', action='store_true',
                        help="Перемещать файлы в корзину вместо полного удаления")
    args = parser.parse_args()

    folder = os.path.abspath(args.folder)
    if not os.path.isdir(folder):
        print(f"Ошибка: папка '{folder}' не существует.")
        return

    print(f"Сканирование папки: {folder}")
    image_files = get_image_files(folder, args.recursive)
    print(f"Найдено изображений: {len(image_files)}")

    if not image_files:
        print("Нет изображений для обработки.")
        return

    print("Вычисление хэшей файлов...")
    duplicate_groups = find_duplicates(image_files)

    if not duplicate_groups:
        print("Дубликаты не найдены.")
        return

    total_duplicates = sum(len(paths) for paths in duplicate_groups.values()) - len(duplicate_groups)
    print(f"\nНайдено дубликатов (файлов к удалению): {total_duplicates}")

    deleted = delete_duplicates(duplicate_groups, args.keep, args.dry_run, args.use_trash)
    if args.dry_run:
        print(f"\nСухой прогон завершён. Было бы удалено {deleted} файлов.")
    else:
        print(f"\nГотово. Удалено файлов: {deleted}")


if __name__ == "__main__":
    main()