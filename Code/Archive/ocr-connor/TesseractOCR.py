from PIL import Image, ImageEnhance, ImageFilter
import pytesseract
import os

ExampleImageLocation = "../../Examples/Cellularised-Example/"

def enhance_image(image):
    image = image.convert("L")
    enhancer = ImageEnhance.Contrast(image)
    image = enhancer.enhance(2)
    enhancer = ImageEnhance.Sharpness(image)
    image = enhancer.enhance(2)
    return image

def ocr_extraction(image_paths):
    for image in image_paths:
        cell = Image.open(image)
        enhanced_cell = enhance_image(cell)
        cell_data = pytesseract.image_to_string(enhanced_cell, config='--psm 6')
        print(f"Data extracted from {image}: {cell_data}")

def get_image_paths():
    image_paths = []
    for file in os.listdir(ExampleImageLocation):
        if file.endswith(".png"):
            image_paths.append(os.path.join(ExampleImageLocation, file))
    return image_paths

if __name__ == "__main__":
    image_paths = get_image_paths()
    ocr_extraction(image_paths)
