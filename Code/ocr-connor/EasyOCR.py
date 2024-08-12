from PIL import Image, ImageEnhance, ImageFilter
import easyocr
import io
import os

# Blocks security warning relating to torch.load in PyTorch library used by EasyOCR
import warnings
warnings.filterwarnings("ignore", category=FutureWarning)


ExampleImageLocation = "../../Examples/Cellularised-Example/"

def enhance_image(image):
    image = image.convert("L")
    enhancer = ImageEnhance.Contrast(image)
    image = enhancer.enhance(2)
    enhancer = ImageEnhance.Sharpness(image)
    image = enhancer.enhance(2)
    return image

def ocr_extraction(image_paths):
    reader = easyocr.Reader(['en'])
    for image_path in image_paths:
        cell = Image.open(image_path)
        enhanced_cell = enhance_image(cell)
        byte_arr = io.BytesIO()
        enhanced_cell.save(byte_arr, format='PNG')
        byte_arr = byte_arr.getvalue()
        cell_data = reader.readtext(byte_arr, detail=0)
        cell_data_text = " ".join(cell_data)
        print(f"Data extracted from {image_path}: {cell_data_text}")

def get_image_paths():
    image_paths = []
    for file in os.listdir(ExampleImageLocation):
        if file.endswith(".png"):
            image_paths.append(os.path.join(ExampleImageLocation, file))
    return image_paths

if __name__ == "__main__":
    image_paths = get_image_paths()
    ocr_extraction(image_paths)
