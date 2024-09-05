import os
import pytesseract
import csv
from PIL import Image

image_directory = 'imageext'
output_csv = 'output.csv'


"""
Extracts text from images in a specified directory and writes the data to a CSV file.

This function processes all PNG images in the `image_directory`, using the filename 
to determine the row and column indices for a table. It extracts text from each 
image using the `pytesseract` OCR engine, cleans up the text, and stores it in a 
dictionary structure. The data is then written into a CSV file.

@param image_directory: A string representing the path to the folder containing the images.
                        Image filenames must follow the format `page_row_col.png`, where 
                        `row` and `col` are the respective table coordinates.
@param output_csv: A string representing the path to the CSV file where the table data will be saved.

@return None. The table data is written directly to the CSV file.

Example:
--------
extract_text_from_images("image_directory", "output.csv")

Notes:
- The `pytesseract` OCR tool must be installed and properly configured.
- The images should be in PNG format and contain text that can be recognized by `pytesseract`.
- The table structure is determined by the row and column indices in the filenames.

Exceptions:
-----------
- Raises `OSError` if image files cannot be opened or processed.
- Raises `ValueError` if image filenames do not follow the expected format.
- If no images are processed, an error message is printed and the function exits.
"""

table_data = {}

for filename in os.listdir(image_directory):
    if filename.endswith(".png"):
        parts = filename.split('_')
        row_index = int(parts[2])
        col_index = int(parts[3].split('.')[0])

        image_path = os.path.join(image_directory, filename)
        image = Image.open(image_path)

        text = pytesseract.image_to_string(image, config='--psm 6 -c preserve_interword_spaces=1')
        
        text = text.strip()
        text = text.replace('\n', ' ')
        text = ' '.join(text.split()) 

        if row_index not in table_data:
            table_data[row_index] = {}
        table_data[row_index][col_index] = text


max_columns = max(max(cols.keys()) for cols in table_data.values())
with open(output_csv, mode='w', newline='') as file:
    writer = csv.writer(file)
    for row_index in sorted(table_data.keys()):
        row = []
        for col_index in range(max_columns + 1):
            cell_text = table_data[row_index].get(col_index, "")
            row.append(cell_text)
        writer.writerow(row)


#############

# max_columns = max(max(cols.keys()) for cols in table_data.values())

# # Add a check to ensure table_data is not empty
# if table_data:
#     max_columns = max(max(cols.keys()) for cols in table_data.values())
# else:
#     print("No data found. Exiting.")
#     max_columns = 0  # Or handle this case as needed
#     return
