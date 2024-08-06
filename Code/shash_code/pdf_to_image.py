from pdf_to_image import convert_from_path
from PIL import Image, ImageEnhance

def enhance_image(image):
    enhancer = ImageEnhance.Contrast(image)
    image = enhancer.enhance(2)  # Increase contrast
    enhancer = ImageEnhance.Sharpness(image)
    image = enhancer.enhance(2)  # Increase sharpness
    return image

def pdf_to_images(pdf_path):
    images = convert_from_path(pdf_path)
    enhanced_images = [enhance_image(image) for image in images]
    return enhanced_images
