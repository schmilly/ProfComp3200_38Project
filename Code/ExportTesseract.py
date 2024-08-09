import os
import pytesseract
import csv
from PIL import Image

image_directory = 'imageext'
output_csv = 'output.csv'

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
