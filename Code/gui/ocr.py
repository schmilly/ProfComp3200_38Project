import fitz  # PyMuPDF
from pdf2image import convert_from_path
from PIL import Image
import pytesseract
import pandas as pd
import time

# Configure Tesseract executable path
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'  # Adjust path as needed

def extract_images_from_pdf(pdf_path):
    images = convert_from_path(pdf_path)
    return images

def perform_ocr_on_image(image):
    text = pytesseract.image_to_string(image)
    return text

def parse_text_to_table(text):
    lines = text.split('\n')
    data = [line.split() for line in lines if line.strip()]
    return data

def convert_table_to_dataframe(table):
    df = pd.DataFrame(table[1:], columns=table[0])
    return df

def ocr_pdf_to_table(pdf_path):
    start_time = time.time()
    images = extract_images_from_pdf(pdf_path)
    all_tables = []

    for image in images:
        text = perform_ocr_on_image(image)
        table = parse_text_to_table(text)
        df = convert_table_to_dataframe(table)
        all_tables.append(df)

    end_time = time.time()
    elapsed_time = end_time - start_time
    return all_tables, elapsed_time
