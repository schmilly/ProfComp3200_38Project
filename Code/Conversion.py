import subprocess
import os

def convert_pdf_to_images(pdf_path, output_folder, image_format='png'):

    os.makedirs(output_folder, exist_ok=True)
    
    #this is the command which converts the pdf. 
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
