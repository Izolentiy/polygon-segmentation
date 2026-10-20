import os
import sys
from PIL import Image

def process_images(input_folder, output_folder):
    """
    Изменяет размер всех JPEG-изображений в input_folder до 512x256 пикселей
    и сохраняет их в output_folder с теми же именами.
    """
    # Проверяем существование входной папки
    if not os.path.isdir(input_folder):
        print(f"Ошибка: папка '{input_folder}' не найдена.")
        return

    # Создаём выходную папку, если её нет
    os.makedirs(output_folder, exist_ok=True)

    # Поддерживаемые расширения (регистронезависимо)
    extensions = ('.jpg', '.jpeg')

    processed = 0
    for filename in os.listdir(input_folder):
        if filename.lower().endswith(extensions):
            input_path = os.path.join(input_folder, filename)
            output_path = os.path.join(output_folder, filename)

            try:
                with Image.open(input_path) as img:
                    # Изменяем размер с использованием фильтра LANCZOS
                    resized = img.resize((512, 256), Image.LANCZOS)
                    resized.save(output_path, 'JPEG')
                    print(f"Обработан: {filename}")
                    processed += 1
            except Exception as e:
                print(f"Ошибка при обработке {filename}: {e}")

    print(f"\nГотово. Обработано файлов: {processed}")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Использование: python resize_folder.py <входная_папка> <выходная_папка>")
        print("Пример: python resize_folder.py ./original_images ./resized_images")
        sys.exit(1)

    input_folder = sys.argv[1]
    output_folder = sys.argv[2]

    process_images(input_folder, output_folder)