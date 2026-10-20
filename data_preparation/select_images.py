#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Скрипт для копирования каждой пятой картинки из папки (с обходом подпапок) в отдельную папку.
При копировании файлы переименовываются в порядковые номера (1, 2, 3, ...) с сохранением расширения.
"""

import os
import argparse
import shutil
import re
from pathlib import Path

# Расширения файлов, которые считаем изображениями
IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp', '.ico'}


def is_image_file(filename):
    """Проверяет, является ли файл изображением по расширению."""
    ext = os.path.splitext(filename)[1].lower()
    return ext in IMAGE_EXTENSIONS


def collect_images(source_dir, recursive=False):
    """
    Собирает все изображения в source_dir.
    Если recursive=True, обходит подпапки.
    Возвращает список абсолютных путей к файлам.
    """
    image_files = []
    if recursive:
        for root, dirs, files in os.walk(source_dir):
            for file in files:
                if is_image_file(file):
                    image_files.append(os.path.join(root, file))
    else:
        for entry in os.listdir(source_dir):
            full_path = os.path.join(source_dir, entry)
            if os.path.isfile(full_path) and is_image_file(entry):
                image_files.append(full_path)
    return image_files


def natural_key(text):
    """
    Преобразует строку в список для естественной сортировки.
    Числовые последовательности превращаются в int, остальное — в строку в нижнем регистре.
    """
    return [int(part) if part.isdigit() else part.lower() for part in re.split(r'(\d+)', text)]


def copy_with_numbering(files, dest_dir, step=5, sort_by='name',
                        zero_padding=None, overwrite=False, dry_run=False):
    """
    Копирует файлы из списка files в dest_dir с переименованием в порядковые номера.
    - step: копируется каждый step-й файл (начиная с первого, т.е. индексы 0, step, 2*step...).
    - sort_by: способ сортировки списка перед выбором ('name', 'mtime', 'natural').
    - zero_padding: количество цифр в имени (если None, вычисляется автоматически).
    - overwrite: если True, перезаписывать существующие файлы, иначе пропускать.
    - dry_run: если True, только выводить информацию, не копируя.
    Возвращает количество скопированных файлов.
    """
    # Сортируем файлы
    if sort_by == 'name':
        files.sort(key=lambda p: os.path.basename(p).lower())
    elif sort_by == 'natural':
        files.sort(key=lambda p: natural_key(os.path.basename(p)))
    elif sort_by == 'mtime':
        files.sort(key=lambda p: os.path.getmtime(p))
    else:
        raise ValueError(f"Неизвестный способ сортировки: {sort_by}")

    # Отбираем каждый step-й файл
    selected = files[::step]  # шаг step, начиная с индекса 0

    # Создаём папку назначения, если её нет
    if not dry_run:
        os.makedirs(dest_dir, exist_ok=True)

    # Определяем количество цифр для нумерации
    total = len(selected)
    if zero_padding is None:
        zero_padding = len(str(total))  # минимальное количество цифр, чтобы вместить все номера
    fmt = f"{{:0{zero_padding}d}}"

    copied = 0
    for idx, src_path in enumerate(selected, start=1):
        # Определяем расширение исходного файла
        ext = os.path.splitext(src_path)[1].lower()
        # Формируем новое имя
        new_name = fmt.format(idx) + ext
        dest_path = os.path.join(dest_dir, new_name)

        # Проверяем, существует ли уже файл в папке назначения
        if not overwrite and os.path.exists(dest_path):
            print(f"Пропуск (файл уже существует): {dest_path}")
            continue

        if dry_run:
            print(f"[dry-run] Будет скопирован:\n  {src_path}\n  -> {dest_path}")
        else:
            try:
                shutil.copy2(src_path, dest_path)  # copy2 сохраняет метаданные
                print(f"Скопирован: {src_path} -> {dest_path}")
                copied += 1
            except (IOError, OSError, shutil.Error) as e:
                print(f"Ошибка копирования {src_path}: {e}")

    return copied


def main():
    parser = argparse.ArgumentParser(
        description="Копирование каждой пятой картинки из папки с перенумерацией."
    )
    parser.add_argument('source_dir', help="Исходная папка с изображениями")
    parser.add_argument('dest_dir', help="Папка назначения, куда копировать")
    parser.add_argument('-s', '--step', type=int, default=5,
                        help="Шаг отбора: копируется каждый STEP-й файл (по умолчанию 5)")
    parser.add_argument('-r', '--recursive', action='store_true',
                        help="Рекурсивно обходить подпапки в source_dir")
    parser.add_argument('--sort-by', choices=['name', 'mtime', 'natural'], default='natural',
                        help="Сортировка файлов перед отбором: name (лексикографически), natural (естественная сортировка чисел), mtime (по времени изменения)")
    parser.add_argument('-z', '--zero-padding', type=int, default=None,
                        help="Количество цифр в нумерации (по умолчанию определяется автоматически)")
    parser.add_argument('-o', '--overwrite', action='store_true',
                        help="Разрешить перезапись существующих файлов в папке назначения")
    parser.add_argument('-n', '--dry-run', action='store_true',
                        help="Только показать, что будет скопировано, без реального копирования")
    args = parser.parse_args()

    source_dir = os.path.abspath(args.source_dir)
    if not os.path.isdir(source_dir):
        print(f"Ошибка: исходная папка '{source_dir}' не существует.")
        return

    dest_dir = os.path.abspath(args.dest_dir)
    # Если папка назначения совпадает с исходной, предупредим
    if source_dir == dest_dir:
        print("Предупреждение: исходная папка и папка назначения совпадают. Файлы будут перезаписаны.")

    print(f"Сбор изображений из: {source_dir} (рекурсивно: {args.recursive})")
    images = collect_images(source_dir, args.recursive)
    print(f"Найдено изображений: {len(images)}")

    if not images:
        print("Нет изображений для обработки.")
        return

    print(f"Отбор каждого {args.step}-го файла после сортировки по {args.sort_by}...")
    copied = copy_with_numbering(
        files=images,
        dest_dir=dest_dir,
        step=args.step,
        sort_by=args.sort_by,
        zero_padding=args.zero_padding,
        overwrite=args.overwrite,
        dry_run=args.dry_run
    )

    if args.dry_run:
        print(f"\nСухой прогон завершён. Будет скопировано файлов: {copied}")
    else:
        print(f"\nГотово. Скопировано файлов: {copied}")


if __name__ == "__main__":
    main()