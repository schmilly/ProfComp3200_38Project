import tkinter as tk
from tkinter import filedialog, messagebox
from pdf2image import convert_from_path
import pytesseract
import pandas as pd
from PIL import Image
import os

def pdf_to_images(pdf_path):
    return convert_from_path(pdf_path)

def extract_text_from_image(image):
    return pytesseract.image_to_string(image)

def extract_tables_from_text(text):
    data = [line.split('\t') for line in text.split('\n') if line.strip()]
    df = pd.DataFrame(data)
    df.dropna(how='all', axis=0, inplace=True)
    df.dropna(how='all', axis=1, inplace=True)
    return df

def process_pdf(pdf_path):
    images = pdf_to_images(pdf_path)
    all_tables = []
    
    for i, image in enumerate(images):
        text = extract_text_from_image(image)
        df = extract_tables_from_text(text)
        
        if not df.empty:
            all_tables.append(df)
            csv_path = f"table_page_{i + 1}.csv"
            df.to_csv(csv_path, index=False)
            print(f"Table saved as {csv_path}")
    
    if not all_tables:
        messagebox.showinfo("Result", "No tables found in the PDF.")
    else:
        messagebox.showinfo("Result", f"Tables saved as CSV files.")

def upload_pdf():
    file_path = filedialog.askopenfilename(filetypes=[("PDF files", "*.pdf")])
    if file_path:
        process_pdf(file_path)

def create_gui():
    root = tk.Tk()
    root.title("PDF Table Extractor")

    upload_button = tk.Button(root, text="Upload PDF", command=upload_pdf)
    upload_button.pack(pady=20)

    root.mainloop()

if __name__ == "__main__":
    create_gui()
