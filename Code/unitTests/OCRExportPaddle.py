import os
import csv
from PIL import Image, ImageEnhance, ImageFilter, ImageTk
import pytesseract
import tkinter as tk
from tkinter import simpledialog, messagebox
from paddleocr import PaddleOCR, draw_ocr
import cv2
import numpy as np

# Load TrOCR model and processor
ocr = PaddleOCR(use_angle_cls=True, lang='en')

image_directory = 'Cellularised-Example'
output_csv = 'output.csv'
table_data = {}
def perform_paddle_ocr(image):
    """Use PaddleOCR to extract text from an image, focusing on numeric content."""
    # Check the image is in the correct format for PaddleOCR
    image_array = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
    
    # Run OCR on the image
    try:
        result = ocr.ocr(image_array, cls=True)
        if result is None or not result:
            print("No text detected in the image.")
            return ''
        
        texts = []
        for line in result:
            if line: 
                for info in line:
                    text = info[1][0]
                    texts.append(text)
        return ' '.join(texts)
    except Exception as e:
        print(f"An error occurred during OCR processing: {e}")
        return ''

def clean_text(text):
    """ Remove unwanted characters and clean text """
    text = text.replace('|', '').strip()  # Remove table borders represented by '|'
    return ' '.join(text.split())  # Normalize whitespace

def preprocess_image(image):
    """ Apply targeted preprocessing to enhance periods in numbers """
    image = image.convert('L')  # Convert to grayscale
    base_width = image.width * 2  # Adjust scale factor as needed
    base_height = image.height * 2
    image = image.resize((base_width, base_height), Image.LANCZOS)

    # Enhance sharpness to make periods in numbers more distinguishable
    enhancer = ImageEnhance.Sharpness(image)
    image = enhancer.enhance(1) 

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

for filename in os.listdir(image_directory):
    if filename.endswith(".png"):
        parts = filename.split('_')
        row_index = int(parts[2])
        col_index = int(parts[3].split('.')[0])

        image_path = os.path.join(image_directory, filename)
        image = Image.open(image_path).convert("RGB")
        processed_image = preprocess_image(image)

        # Perform OCR using Tesseract
        # text = pytesseract.image_to_string(processed_image, config='--oem 1 --psm 6')
        # cleaned_text = clean_text(text)

        # Conditional fallback to paddle if the text is empty or mostly numeric
        # if not cleaned_text or is_mostly_numeric(cleaned_text):
        cleaned_text = perform_paddle_ocr(processed_image)

        # Verify and possibly correct OCR results using GUI
        corrected_text = verify_ocr_results(filename, processed_image, cleaned_text)
        print(f"OCR Result for {filename}: {corrected_text}")  # Debug output

        if row_index not in table_data:
            table_data[row_index] = {}
        table_data[row_index][col_index] = corrected_text

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

print("OCR verification complete. Results saved to CSV.")
