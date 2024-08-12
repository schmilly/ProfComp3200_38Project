from PIL import Image
import pytesseract
import os
import cv2
import numpy as np

OutputLocation = "../../Examples/Cellularised-Example/"

def upscale_image(cell):
    open_cv_image = np.array(cell)
    open_cv_image = cv2.cvtColor(open_cv_image, cv2.COLOR_RGB2BGR)
    original_size = open_cv_image.shape[:2]
    upscaled_cell = cv2.resize(open_cv_image, (original_size[1] * 2, original_size[0] * 2), interpolation=cv2.INTER_CUBIC)
    upscaled_cell = Image.fromarray(cv2.cvtColor(upscaled_cell, cv2.COLOR_BGR2RGB))
    return upscaled_cell


def ocr_extraction(image_paths):
    for image_path in image_paths:
        cell = Image.open(image_path)
        upscaled_cell = upscale_image(cell)
        cell_data = pytesseract.image_to_string(upscaled_cell, config='--psm 6 --oem 3', lang='eng')
        print(f"Data extracted from {cell}: {cell_data}")

def get_image_paths():
    image_paths = []
    for file in os.listdir(OutputLocation):
        if file.endswith(".png"):
            image_paths.append(os.path.join(OutputLocation, file))
    return image_paths

if __name__ == "__main__":
    image_paths = get_image_paths()
    extracted_data = ocr_extraction(image_paths)
