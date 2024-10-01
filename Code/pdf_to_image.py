# pdf_to_image.py
import subprocess
import os
from pdf2image import convert_from_path
from PIL import Image, ImageEnhance, ImageFilter

def enhance_image(image):
    enhancer = ImageEnhance.Contrast(image)
    image = enhancer.enhance(2)  # Increase contrast
    enhancer = ImageEnhance.Sharpness(image)
    image = enhancer.enhance(2)  # Increase sharpness
    image = image.filter(ImageFilter.MedianFilter(size=3))  #Reduces noice - found code on stackflow
    return image

def pdf_to_images(pdf_path):
    images = convert_from_path(pdf_path,200)
    #enhanced_images = [enhance_image(image) for image in images]
    return images



def convert_pdf_to_images(pdf_path, output_folder, image_format='png'):
    """
    Converts a PDF file into images, saving them in a specified folder.

    This function uses the `pdftoppm` tool to convert each page of the input PDF file 
    into an image. The images are saved in the specified output folder with a 
    filename prefix of 'page'. The image format can be customized.

    @param pdf_path: A string representing the path to the PDF file to be converted.
    @param output_folder: A string representing the path to the folder where the images 
                          will be saved.
    @param image_format: A string representing the image format (default is 'png').
                         Can be set to other formats like 'jpeg' if supported by `pdftoppm`.

    @return A list of strings, each representing the file path to a generated image.

    Example:
    --------
    convert_pdf_to_images("document.pdf", "output_images", "jpeg")

    Notes:
    - The `pdftoppm` tool must be installed on your system (e.g., using Homebrew and Poppler for macOS).
    - The output folder will be created if it does not exist.
    - This function assumes that the `pdftoppm` command-line tool is available and accessible.

    Exceptions:
    -----------
    - Raises `subprocess.CalledProcessError` if the PDF conversion process fails.
    """
    os.makedirs(output_folder, exist_ok=True)
    
    conversion = [
        'pdftoppm',
        '-{}'.format(image_format),
        pdf_path,
        os.path.join(output_folder, 'page')
    ]

    subprocess.run(conversion, check=True)
    
    image_files = sorted([
        os.path.join(output_folder, f) for f in os.listdir(output_folder)
        if f.endswith(f'.{image_format}')
    ])
    
    return image_files

# Example usage - this will be changed when the GUI is established so we can drop the pdf file in, and will need integration. (In README need homebrew + poppler installed).

#  if __name__ == "__main__":
#     pdf_path = 'path_to_your_pdf.pdf'  # Replace with the path to your PDF file
#     output_folder = 'output_folder_path'  # Replace with the desired output folder path
#     images = convert_pdf_to_images(pdf_path, output_folder)
#     for image in images:
#         print(f"Generated image: {image}") 
