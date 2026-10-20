from pycocotools.coco import COCO
import numpy as np
import cv2
import os

def hex_to_bgr(hex_color: str):
    hex_color = hex_color.lstrip("#")
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)
    return (b, g, r)

# цвета из CVAT по имени класса
label_colors_hex = {
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

coco = COCO("instances_default.json")

# category_id -> BGR
cat_id_to_color = {}
for cat in coco.loadCats(coco.getCatIds()):
    name = cat["name"]                     # должно совпасть с ключами выше
    hex_color = label_colors_hex.get(name, "#000000")
    cat_id_to_color[cat["id"]] = hex_to_bgr(hex_color)

os.makedirs("out_images", exist_ok=True)

img_ids = coco.getImgIds()

for img_id in img_ids:
    img_info = coco.loadImgs(img_id)[0]
    w, h = img_info["width"], img_info["height"]

    # фон пока чёрный
    canvas = np.zeros((h, w, 3), dtype=np.uint8)

    ann_ids = coco.getAnnIds(imgIds=img_id)
    anns = coco.loadAnns(ann_ids)

    for ann in anns:
        cat_id = ann["category_id"]
        color = cat_id_to_color.get(cat_id, (0, 0, 0))

        mask = coco.annToMask(ann)   # 0/1
        canvas[mask == 1] = color

    # если хочешь, чтобы пустые пиксели тоже были "background",
    # то они уже и так чёрные (#000000), так что дополнительная заливка не нужна

    file_stem = os.path.splitext(img_info["file_name"])[0]
    out_path = os.path.join("out_images", file_stem + ".png")
    cv2.imwrite(out_path, canvas)
