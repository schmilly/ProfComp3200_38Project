import os
import csv
from PIL import Image, ImageEnhance, ImageFilter, ImageTk
import pytesseract
import tkinter as tk
from tkinter import simpledialog, messagebox
from paddleocr import PaddleOCR, draw_ocr
import cv2
import numpy as np

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
for filename in os.listdir(image_directory):
    if filename.endswith(".png"):
        parts = filename.split('_')
        row_index = int(parts[2])
        col_index = int(parts[3].split('.')[0])

        image_path = os.path.join(image_directory, filename)
        image = Image.open(image_path).convert("RGB")
        processed_image = preprocess_image(image)
        original_text, original_confidence = perform_paddle_ocr(image, return_confidence=True)
        processed_text, processed_confidence = perform_paddle_ocr(processed_image, return_confidence=True)

        if original_confidence > processed_confidence:
            final_text = original_text
            final_confidence = original_confidence
            final_image = image 
        else:
            final_text = processed_text
            final_confidence = processed_confidence
            final_image = processed_image 
        # Perform OCR using Tesseract
        # text = pytesseract.image_to_string(processed_image, config='--oem 1 --psm 6')
        # cleaned_text = clean_text(text)

        if col_index == 0 and final_confidence == 0:
            continue

        total += 1
        
        if final_confidence < 0.80:
            bad += 1
            print(f"Review needed for {filename}: {final_text} (Confidence: {final_confidence})")
            # To verify text via GUI manually for low confidence values
            #final_text = verify_ocr_results(filename, final_image, final_text) 
            #print(f"OCR Result for {filename}: {corrected_text}")  # Debug output

        # Conditional fallback to paddle if the text is empty or mostly numeric
        # if not cleaned_text or is_mostly_numeric(cleaned_text):
        #cleaned_text = perform_paddle_ocr(processed_image)

        if row_index not in table_data:
            table_data[row_index] = {}
        table_data[row_index][col_index] = final_text

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
print(f"percentage less than 65 confidence score is {bad/total*100}% with {bad} possibly wrong")
print("OCR verification complete. Results saved to CSV.")
