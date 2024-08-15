import os
import csv
from PIL import Image, ImageEnhance, ImageFilter, ImageTk
import pytesseract
import tkinter as tk
from tkinter import simpledialog, messagebox
from paddleocr import PaddleOCR, draw_ocr
import cv2
import numpy as np
import easyocr  # Import EasyOCR

# Create an EasyOCR reader instance
reader = easyocr.Reader(['en'], gpu=False)  # Set 'gpu=True' if GPU is available

def perform_easyocr(image):
    """Perform OCR using EasyOCR and return text with confidence score."""
    results = reader.readtext(np.array(image), detail=1, paragraph=False)
    texts = [res[1] for res in results]
    confidences = [res[2] for res in results if res[2] > 0]  # Filter zero confidence

    if confidences:
        average_confidence = sum(confidences) / len(confidences)
        full_text = ' '.join(texts)
        return full_text, average_confidence
    else:
        return '', 0
# Load PaddleOCR model and processor
ocr = PaddleOCR(use_angle_cls=True, lang='en',rec_model_dir='en_PP-OCRv4_rec',
    version='PP-OCRv4',
    det_db_thresh=0.35,
    det_db_box_thresh=0.45,
    det_db_unclip_ratio=1.8,
    cls_thresh=0.95,
    use_space_char=True,
    rec_image_shape='3, 48, 320',
    det_limit_side_len=960)
import logging

# Set all existing loggers to WARNING
for logger_name in logging.root.manager.loggerDict:
    logging.getLogger(logger_name).setLevel(logging.WARNING)


image_directory = 'Austria'
output_csv = 'output.csv'
table_data = {}
def perform_paddle_ocr(image, return_confidence=False):
    """Extract text from an image along with confidence scores."""
    image_array = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
    try:
        result = ocr.ocr(image_array, cls=True)
        if not result:
            print("No text detected by PaddleOCR.")
            return ('', 0) if return_confidence else ''

        texts = []
        confidences = []
        for line in result:
            if line:
                for info in line:
                    text = info[1][0]
                    confidence = info[1][1]
                    texts.append(text)
                    confidences.append(confidence)

        combined_text = ' '.join(texts)
        average_confidence = sum(confidences) / len(confidences) if confidences else 0
        return (combined_text, average_confidence) if return_confidence else combined_text
    except Exception as e:
        print(f"An error occurred during OCR processing: {e}")
        return ('', 0) if return_confidence else ''


def clean_text(text):
    """ Remove unwanted characters and clean text """
    text = text.replace('|', '').strip()  # Remove table borders represented by '|'
    return ' '.join(text.split())  # whitespace

def preprocess_image(image):
    """ Apply targeted preprocessing to enhance periods in numbers """
    image = image.convert('L')  # Convert to grayscale
    base_width = image.width * 2  
    base_height = image.height * 2
    image = image.resize((base_width, base_height), Image.LANCZOS)

    # Enhance sharpness to make periods in numbers more distinguishable
    enhancer = ImageEnhance.Sharpness(image)
    image = enhancer.enhance(2) 

    # Increase contrast to make the text stand out more
    enhancer = ImageEnhance.Contrast(image)
    image = enhancer.enhance(4)  

    # Denoise enlarged image
    image = image.filter(ImageFilter.MedianFilter(size=3))

    return image.convert('RGB') 


def is_mostly_numeric(text):
    """ Determine if the text is mostly numeric """
    digits = sum(c.isdigit() or c == '.' for c in text) 
    letters = sum(c.isalpha() for c in text)
    return digits > letters


def verify_ocr_results(filename, image, ocr_text):
    """Create a Tkinter dialog to display the image and accept user corrections"""
    root = tk.Tk()
    root.title("Verify OCR Results")
    tk.Label(root, text=f"Filename: {filename}").pack()

    # Display the image after processing
    img = ImageTk.PhotoImage(image)
    panel = tk.Label(root, image=img)
    panel.image = img
    panel.pack()

    # Display the OCR result and provides an entry for corrections
    tk.Label(root, text="OCR Text:").pack()
    ocr_var = tk.StringVar(root, value=ocr_text)
    ocr_entry = tk.Entry(root, textvariable=ocr_var)
    ocr_entry.pack()

    # Button to confirm the correction
    def confirm():
        corrected_text = ocr_entry.get()
        root.destroy()
        return corrected_text

    confirm_button = tk.Button(root, text="Confirm", command=confirm)
    confirm_button.pack()

    root.mainloop()
    return ocr_var.get()

total = 0
bad = 0
easyocr_count = 0
paddleocr_count = 0
for filename in os.listdir(image_directory):
    if filename.endswith(".png"):
        parts = filename.split('_')
        row_index = int(parts[2])
        col_index = int(parts[3].split('.')[0])

        image_path = os.path.join(image_directory, filename)
        image = Image.open(image_path).convert("RGB")
        processed_image = preprocess_image(image)
        # OCR with PaddleOCR
        original_text, original_confidence = perform_paddle_ocr(image, return_confidence=True)
        processed_text, processed_confidence = perform_paddle_ocr(processed_image, return_confidence=True)

        # OCR with EasyOCR
        easy_original_text, easy_original_conf = perform_easyocr(image)
        easy_processed_text, easy_processed_conf = perform_easyocr(processed_image)

        # Determine the highest confidence result
        best_result = max(
            (original_text, original_confidence, 'Original Image, PaddleOCR'),
            (processed_text, processed_confidence, 'Processed Image, PaddleOCR'),
            (easy_original_text, easy_original_conf, 'Original Image, EasyOCR'),
            (easy_processed_text, easy_processed_conf, 'Processed Image, EasyOCR'),
            key=lambda x: x[1]  # Compare by confidence
        )

        if col_index == 0 and best_result[1] == 0:
            continue
        if 'EasyOCR' in best_result[2]:
            easyocr_count += 1
        else:
            paddleocr_count += 1
          
        total += 1
      
        if best_result[1] < 0.80:
            bad += 1
            print(f"Review needed for {filename}: {best_result[0]} (Confidence: {best_result[1]}, Source: {best_result[2]})")
            # To verify text via GUI manually for low confidence values
            #final_text = verify_ocr_results(filename, final_image, final_text) 
            #print(f"OCR Result for {filename}: {corrected_text}")  # Debug output

        if row_index not in table_data:
            table_data[row_index] = {}
        table_data[row_index][col_index] = best_result[0]

# Write the table data to a CSV file
max_columns = max(max(cols.keys()) for cols in table_data.values())
with open(output_csv, mode='w', newline='') as file:
    writer = csv.writer(file)
    for row_index in sorted(table_data.keys()):
        row = []
        for col_index in range(max_columns + 1):
            cell_text = table_data[row_index].get(col_index, "")
            row.append(cell_text)
        writer.writerow(row)
print(f"percentage less than 80 confidence score is {bad/total*100}% with {bad} possibly wrong")
print("OCR verification complete. Results saved to CSV.")
print(f"Results using EasyOCR: {easyocr_count}")
print(f"Results using PaddleOCR: {paddleocr_count}")
