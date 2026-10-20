#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Сборка датасета для обучения одним запуском: raw-кадры -> готовые пары image/mask.

Шаги:
1. копирование raw -> duplicate_free и удаление дубликатов (remove_duplicates.py);
2. выбор каждого N-го кадра с нумерацией 001, 002, ... (select_images.py);
3. уменьшение кадров до 512x256 (squeeze_images.py);
4. генерация цветных PNG-масок из COCO JSON, выгруженного из CVAT (visualize_annotations.py);
5. сборка dataset/image и dataset/mask и удаление неверно размеченных пар.

Пример (из любой папки):
    python data_preparation/build_dataset.py
"""

import argparse
import os
import shutil
import sys

import cv2
import numpy as np
from pycocotools.coco import COCO

from remove_duplicates import find_duplicates, delete_duplicates, get_image_files
from select_images import collect_images, copy_with_numbering
from squeeze_images import process_images

HERE = os.path.dirname(os.path.abspath(__file__))

# Цвета классов из CVAT по имени метки (RGB hex); фон остаётся чёрным.
LABEL_COLORS_HEX = {
    "blue": "#2a7dd1",
    "green": "#24b353",
    "light_green": "#ddff33",
    "dark_red": "#883131",
    "red": "#fa3253",
    "dark_gray": "#818181",
    "gray": "#bdbdbd",
    "white": "#ffffff",
    "purple": "#8c78f0",
}

# Номера кадров с неверной разметкой, отбракованные вручную (остаётся 126 пар из 146).
DEFAULT_EXCLUDE = [*range(51, 59), 73, 77, *range(87, 90), *range(102, 107), 132, 133]


def hex_to_bgr(hex_color):
    hex_color = hex_color.lstrip("#")
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (0, 2, 4))
    return (b, g, r)


def step_remove_duplicates(raw_dir, dst_dir, keep, use_trash):
    print(f"\n[1/5] Копирование {raw_dir} -> {dst_dir} и удаление дубликатов")
    shutil.copytree(raw_dir, dst_dir)
    groups = find_duplicates(get_image_files(dst_dir))
    deleted = delete_duplicates(groups, keep, False, use_trash) if groups else 0
    left = len(get_image_files(dst_dir))
    print(f"Удалено дубликатов: {deleted}, осталось кадров: {left}")


def step_select(src_dir, dst_dir, step):
    print(f"\n[2/5] Выбор каждого {step}-го кадра")
    copied = copy_with_numbering(collect_images(src_dir), dst_dir, step=step, sort_by="natural")
    print(f"Выбрано кадров: {copied}")


def step_squeeze(src_dir, dst_dir):
    print("\n[3/5] Уменьшение до 512x256")
    process_images(src_dir, dst_dir)


def step_masks(annotations, dst_dir):
    print("\n[4/5] Генерация масок из разметки CVAT")
    coco = COCO(annotations)
    cat_colors = {
        cat["id"]: hex_to_bgr(LABEL_COLORS_HEX.get(cat["name"], "#000000"))
        for cat in coco.loadCats(coco.getCatIds())
    }
    os.makedirs(dst_dir)
    for img_id in coco.getImgIds():
        info = coco.loadImgs(img_id)[0]
        canvas = np.zeros((info["height"], info["width"], 3), dtype=np.uint8)
        for ann in coco.loadAnns(coco.getAnnIds(imgIds=img_id)):
            canvas[coco.annToMask(ann) == 1] = cat_colors.get(ann["category_id"], (0, 0, 0))
        stem = os.path.splitext(info["file_name"])[0]
        cv2.imwrite(os.path.join(dst_dir, stem + ".png"), canvas)
    print(f"Создано масок: {len(os.listdir(dst_dir))}")


def step_assemble(images_dir, masks_dir, out_dir, exclude):
    print("\n[5/5] Сборка датасета")
    out_images, out_masks = os.path.join(out_dir, "image"), os.path.join(out_dir, "mask")
    os.makedirs(out_images)
    os.makedirs(out_masks)
    skipped = 0
    for name in sorted(os.listdir(images_dir)):
        stem = os.path.splitext(name)[0]
        mask_path = os.path.join(masks_dir, stem + ".png")
        if int(stem) in exclude or not os.path.exists(mask_path):
            skipped += 1
            continue
        shutil.copy2(os.path.join(images_dir, name), os.path.join(out_images, name))
        shutil.copy2(mask_path, os.path.join(out_masks, stem + ".png"))
    print(f"Пар в датасете: {len(os.listdir(out_images))} (пропущено: {skipped})")
    print(f"Готово: {out_dir}")


def main():
    parser = argparse.ArgumentParser(description="Сборка датасета сегментации из raw-кадров.")
    parser.add_argument("--raw", default=os.path.join(HERE, "data", "raw"),
                        help="Папка с исходными кадрами (по умолчанию data_preparation/data/raw)")
    parser.add_argument("--work-dir", default=os.path.join(HERE, "data"),
                        help="Папка для промежуточных результатов (по умолчанию data_preparation/data)")
    parser.add_argument("--annotations", default=os.path.join(HERE, "instances_default.json"),
                        help="COCO JSON из CVAT (по умолчанию data_preparation/instances_default.json)")
    parser.add_argument("--output", default=os.path.join(HERE, "..", "dataset"),
                        help="Папка готового датасета (по умолчанию dataset в корне проекта)")
    parser.add_argument("--step", type=int, default=8, help="Брать каждый N-й кадр (по умолчанию 8)")
    parser.add_argument("--exclude", type=int, nargs="*", default=DEFAULT_EXCLUDE,
                        help="Номера кадров, которые нужно исключить (по умолчанию — отбракованные в работе)")
    parser.add_argument("--keep", choices=["first", "last", "newest", "oldest"], default="last",
                        help="Какой файл из дубликатов оставить (по умолчанию last)")
    parser.add_argument("--use-trash", action="store_true",
                        help="Отправлять дубликаты в корзину (только из копии raw, обычно не нужно)")
    parser.add_argument("--force", action="store_true",
                        help="Удалить и пересоздать промежуточные папки и датасет, если они уже есть")
    args = parser.parse_args()

    raw = os.path.abspath(args.raw)
    work = os.path.abspath(args.work_dir)
    out = os.path.abspath(args.output)
    dup_free, selected, squeezed, masks = (os.path.join(work, n) for n in
                                           ("duplicate_free", "selected", "squeezed", "masks"))

    if not os.path.isdir(raw):
        sys.exit(f"Ошибка: папка с исходными кадрами не найдена: {raw}")
    if not os.path.isfile(args.annotations):
        sys.exit(f"Ошибка: файл разметки не найден: {args.annotations}")

    created = [dup_free, selected, squeezed, masks, out]
    existing = [p for p in created if os.path.exists(p)]
    if existing and not args.force:
        sys.exit("Ошибка: уже существуют папки:\n  " + "\n  ".join(existing) +
                 "\nУдалите их или запустите с --force, чтобы пересоздать.")
    for path in existing:
        shutil.rmtree(path)

    step_remove_duplicates(raw, dup_free, args.keep, args.use_trash)
    step_select(dup_free, selected, args.step)
    step_squeeze(selected, squeezed)
    step_masks(args.annotations, masks)
    step_assemble(squeezed, masks, out, set(args.exclude))


if __name__ == "__main__":
    main()
