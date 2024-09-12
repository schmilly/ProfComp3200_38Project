import os
import csv
from PIL import Image, ImageEnhance, ImageFilter
import torch
from transformers import TrOCRProcessor, VisionEncoderDecoderModel

image_directory = 'imageext'
output_csv = 'output.csv'

#Load TrOCR model and processor
processor = TrOCRProcessor.from_pretrained('microsoft/trocr-large-printed')
model = VisionEncoderDecoderModel.from_pretrained('microsoft/trocr-large-printed')

#Set the device (GPU if available)
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model.to(device)

table_data = {}

def clean_text(text):
    """ Clean text from OCR to remove unwanted characters """
    text = text.replace('|', '').strip()  # Remove table borders represented by '|'
    return ' '.join(text.split())  # Normalize whitespace

def preprocess_image(image):
    """ Apply image preprocessing enhancements """
    image = image.convert('L')  # Convert to grayscale to focus on intensity information
    image = ImageEnhance.Contrast(image).enhance(3)  # Significantly increase contrast
    image = image.filter(ImageFilter.SHARPEN)  # Sharpen the image to enhance edges
    image = image.convert('RGB')
    return image

for filename in os.listdir(image_directory):
    if filename.endswith(".png"):
        parts = filename.split('_')
        row_index = int(parts[2])
        col_index = int(parts[3].split('.')[0])

        image_path = os.path.join(image_directory, filename)
        image = Image.open(image_path).convert("RGB")
        image = preprocess_image(image)  # Apply preprocessing

        #Convert the processed image for TrOCR
        pixel_values = processor(images=image, return_tensors="pt").pixel_values.to(device)
        
        #Generate text using TrOCR
        generated_ids = model.generate(pixel_values)
        text = processor.batch_decode(generated_ids, skip_special_tokens=True)[0]
        text = clean_text(text)

        print(f"OCR Result for {filename}: {text}")  #Debug

        if row_index not in table_data:
            table_data[row_index] = {}
        table_data[row_index][col_index] = text

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
