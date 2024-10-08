# pdf_to_image.py

import os
import fitz  # PyMuPDF
from PIL import Image, ImageEnhance, ImageFilter
import io

def enhance_image(image):
    """
    Enhances the image by increasing contrast and sharpness and reducing noise.

    @param image: A PIL Image object.
    @return: Enhanced PIL Image object.
    """
    image = image.convert('L')  # Convert to grayscale
    enhancer = ImageEnhance.Contrast(image)
    image = enhancer.enhance(2)  # Increase contrast
    enhancer = ImageEnhance.Sharpness(image)
    image = enhancer.enhance(3)  # Increase sharpness
    image = image.filter(ImageFilter.MedianFilter(size=3))  # Reduces noise
    return image.convert('RGB')

def pdf_to_images(pdf_path, dpi=400, rotation_angle=0):
    """
    Converts a PDF file into a list of PIL images.

    @param pdf_path: Path to the PDF file.
    @param zoom_x: Horizontal zoom factor (default is 2.0).
    @param zoom_y: Vertical zoom factor (default is 2.0).
    @param rotation_angle: Rotation angle in degrees (default is 0).
    @return: List of PIL Image objects.
    """
    doc = fitz.open(pdf_path)
    images = []
    zoom = dpi / 72  # Calculate zoom factor
    mat = fitz.Matrix(zoom, zoom).prerotate(rotation_angle)
    for page_num in range(len(doc)):
        page = doc.load_page(page_num)  # Load page
        pix = page.get_pixmap(matrix=mat, alpha=False)
        image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        image = enhance_image(image)  # Apply image enhancement
        images.append(image)
    return images

def convert_pdf_to_images(pdf_path, output_folder, image_format='png', zoom_x=2.0, zoom_y=2.0, rotation_angle=0):
    """
    Converts a PDF file into images, saving them in a specified folder.

    This function uses PyMuPDF to render each page of the input PDF file 
    into an image. The images are saved in the specified output folder with a 
    filename prefix of 'page'. The image format can be customized.

    @param pdf_path: Path to the PDF file to be converted.
    @param output_folder: Path to the folder where the images will be saved.
    @param image_format: Image format (default is 'png'). Can be 'jpeg', 'png', etc.
    @param zoom_x: Horizontal zoom factor (default is 2.0).
    @param zoom_y: Vertical zoom factor (default is 2.0).
    @param rotation_angle: Rotation angle in degrees (default is 0).
    @return: List of strings, each representing the file path to a generated image.

    Example:
    --------
    convert_pdf_to_images("document.pdf", "output_images", "jpeg")

    Notes:
    - The output folder will be created if it does not exist.
    - This function uses PyMuPDF for rendering.
    """
    os.makedirs(output_folder, exist_ok=True)
    image_files = []
    with fitz.open(pdf_path) as doc:
        for page_number, page in enumerate(doc, start=1):
            mat = fitz.Matrix(zoom_x, zoom_y).prerotate(rotation_angle)
            pix = page.get_pixmap(matrix=mat)
            output_file = os.path.join(output_folder, f'page_{page_number}.{image_format}')
            pix.save(output_file)
            image_files.append(output_file)
    return image_files
