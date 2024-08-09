# main.py
from table_divider import TableDividerApp
import tkinter as tk
from tkinter import filedialog
from pdf_to_image import pdf_to_images
import os

if __name__ == "__main__":
    root = tk.Tk()
    root.withdraw() 

    pdf_path = filedialog.askopenfilename(
        title="Select PDF File",
        filetypes=[("PDF Files", "*.pdf")],
        initialdir="Examples" 
    )

    if pdf_path:
        images = pdf_to_images(pdf_path)
        root.deiconify()  
        app = TableDividerApp(root, images)
        root.mainloop()
    else:
        print("No file selected.")
