import os
import csv
from PIL import Image, ImageEnhance, ImageFilter
import torch
from transformers import TrOCRProcessor, VisionEncoderDecoderModel
import pytesseract

image_directory = 'imageext'
output_csv = 'output.csv'


"""
Extracts text from images in a specified directory using both Tesseract OCR and TrOCR as a fallback.

This function processes all PNG images in the `image_directory`, applying preprocessing
to enhance the image quality for OCR. It first attempts to extract text using Tesseract OCR.
If the extracted text is empty or mostly numeric, it falls back to using TrOCR for text extraction.
The extracted data is stored in a dictionary and written to a CSV file.

@param image_directory: A string representing the path to the folder containing the images.
                        Image filenames must follow the format `page_row_col.png`, where 
                        `row` and `col` are the respective table coordinates.
@param output_csv: A string representing the path to the CSV file where the table data will be saved.

@return None. The table data is written directly to the CSV file.

Example:
--------
extract_text_from_images_with_fallback("image_directory", "output.csv")

Notes:
- The function uses both `pytesseract` for initial OCR and `TrOCR` as a fallback if the text is empty
    or mostly numeric.
- Images are preprocessed by enhancing contrast, sharpening, and converting to grayscale before
    performing OCR.
- The `pytesseract` OCR tool and the Hugging Face `TrOCR` model must be installed and configured.
- This function assumes the filenames follow the format `page_row_col.png` to extract row and column indices.

Exceptions:
-----------
- Raises `OSError` if image files cannot be opened or processed.
- Raises `ValueError` if image filenames do not follow the expected format.
- If the system does not have a CUDA-compatible GPU, the model will run on the CPU, which may result in slower performance.
"""

#Load TrOCR model and processor
processor = TrOCRProcessor.from_pretrained('microsoft/trocr-large-printed')
model = VisionEncoderDecoderModel.from_pretrained('microsoft/trocr-large-printed')

#Set the device
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model.to(device)

table_data = {}

def clean_text(text):
    text = text.replace('|', '').strip()  # Remove table borders represented by '|'
    return ' '.join(text.split())  # Normalize whitespace

def preprocess_image(image):
    image = image.convert('L')  # Convert to grayscale to focus on intensity information
    image = ImageEnhance.Contrast(image).enhance(3)  # Significantly increase contrast
    image = image.filter(ImageFilter.SHARPEN)  # Sharpen the image to enhance edges
    image = image.convert('RGB')
    return image

def fallback_trocr(image):
    """ Perform OCR using TrOCR without preprocessing """
    pixel_values = processor(images=image, return_tensors="pt").pixel_values.to(device)
    generated_ids = model.generate(pixel_values, max_new_tokens=50)
    return processor.batch_decode(generated_ids, skip_special_tokens=True)[0]

def is_mostly_numeric(text):
    digits = sum(c.isdigit() for c in text)
    letters = sum(c.isalpha() for c in text)
    return digits > letters

for filename in os.listdir(image_directory):
    if filename.endswith(".png"):
        parts = filename.split('_')
        row_index = int(parts[2])
        col_index = int(parts[3].split('.')[0])

        image_path = os.path.join(image_directory, filename)
        image = Image.open(image_path).convert("RGB")
        processed_image = preprocess_image(image)  # Apply preprocessing

        #Perform OCR using Tesseract
        text = pytesseract.image_to_string(processed_image, config='--psm 6')
        cleaned_text = clean_text(text)

        #Conditional fallback to TrOCR if the text is empty or mostly numeric
        if not cleaned_text or is_mostly_numeric(cleaned_text):
            fallback_text = fallback_trocr(image)
            cleaned_text = fallback_text if fallback_text else cleaned_text

        print(f"OCR Result for {filename}: {cleaned_text}")  #Debug 

        if row_index not in table_data:
            table_data[row_index] = {}
        table_data[row_index][col_index] = cleaned_text

#Write the table data to a CSV file
max_columns = max(max(cols.keys()) for cols in table_data.values())
with open(output_csv, mode='w', newline='') as file:
    writer = csv.writer(file)
    for row_index in sorted(table_data.keys()):
        row = []
        for col_index in range(max_columns + 1):
            cell_text = table_data[row_index].get(col_index, "")
            row.append(cell_text)
        writer.writerow(row)
