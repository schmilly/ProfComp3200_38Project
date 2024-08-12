import os
import csv
import torch
import logging
import warnings
from PIL import Image
from transformers import TrOCRProcessor, VisionEncoderDecoderModel
from image_preprocessor import ImagePreprocessor  # Import the ImagePreprocessor class

# Suppress specific warning messages
warnings.filterwarnings("ignore", message="Some weights of.*VisionEncoderDecoderModel.*were not initialized.*")
warnings.filterwarnings("ignore", message="You should probably TRAIN this model.*")
warnings.filterwarnings("ignore", category=FutureWarning, module="transformers.clean_up_tokenization_spaces")


# Set logging level to ERROR or CRITICAL to suppress unnecessary info and warnings
logging.getLogger("transformers").setLevel(logging.ERROR)

class OCRProcessor:
    def __init__(self, model_name='microsoft/trocr-large-printed', contrast=3, sharpness=2):
        # Initialize TrOCR model and processor
        self.processor = TrOCRProcessor.from_pretrained(model_name)
        self.model = VisionEncoderDecoderModel.from_pretrained(model_name)
        
        # Set the device (GPU if available)
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model.to(self.device)

        # Initialize the ImagePreprocessor
        self.preprocessor = ImagePreprocessor(contrast=contrast, sharpness=sharpness)

        self.max_new_tokens = 40

    def trocr_ocr(self, image):
        """Perform OCR using the TrOCR model."""
        pixel_values = self.processor(images=image, return_tensors="pt").pixel_values.to(self.device)
        generated_ids = self.model.generate(pixel_values, max_new_tokens=self.max_new_tokens)
        
        text = self.processor.batch_decode(generated_ids, skip_special_tokens=True, clean_up_tokenization_spaces=True)[0]
        
        return self.clean_text(text)
    
    def clean_text(self, text):
        """Clean text from OCR to remove unwanted characters."""
        text = text.replace('|', '').strip()  # Remove table borders represented by '|'
        return ' '.join(text.split())  # Normalize whitespace

    def process_image(self, image_path):
        """Preprocess and perform OCR on an image."""
        image = Image.open(image_path).convert("RGB")
        
        # Apply preprocessing
        image = self.preprocessor.preprocess(image)

        # Generate text using TrOCR
        return self.trocr_ocr(image)

    def process_directory(self, image_directory, output_csv):
        """Process all images in a directory and output results to a CSV file."""
        table_data = {}

        for filename in os.listdir(image_directory):
            if filename.endswith(".png"):
                parts = filename.split('_')
                try:
                    row_index = int(parts[2])
                    col_index = int(parts[3].split('.')[0])
                except (IndexError, ValueError):
                    print(f"Skipping file with unexpected format: {filename}")
                    continue

                image_path = os.path.join(image_directory, filename)
                text = self.process_image(image_path)
                print(f"OCR Result for {filename}: {text}")  # Debug

                if row_index not in table_data:
                    table_data[row_index] = {}
                table_data[row_index][col_index] = text

        self.write_to_csv(table_data, output_csv)

    def write_to_csv(self, table_data, output_csv):
        """Write the table data to a CSV file."""
        if not table_data:
            print("No data found. Exiting.")
            return
        
        max_columns = max(max(cols.keys()) for cols in table_data.values())
        with open(output_csv, mode='w', newline='') as file:
            writer = csv.writer(file)
            for row_index in sorted(table_data.keys()):
                row = []
                for col_index in range(max_columns + 1):
                    cell_text = table_data[row_index].get(col_index, "")
                    row.append(cell_text)
                writer.writerow(row)


if __name__ == "__main__":
    image_directory = 'imageext'
    output_csv = 'output.csv'
    
    ocr_processor = OCRProcessor()
    ocr_processor.process_directory(image_directory, output_csv)
