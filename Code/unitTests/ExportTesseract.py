import os
import pytesseract
import csv
from PIL import Image
from image_preprocessor import ImagePreprocessor  # Import the ImagePreprocessor class

def main_function(image_directory='test_images', output_csv='output.csv'):
    table_data = {}

    # Initialize the ImagePreprocessor
    preprocessor = ImagePreprocessor(contrast=3, sharpness=2)

    for filename in os.listdir(image_directory):
        if filename.endswith(".png"):
            parts = filename.split('_')
            
            # Assuming the format: page_iiicgko_row_col.png
            try:
                row_index = int(parts[-2])  # The second last part is the row index
                col_index = int(parts[-1].split('.')[0])  # The last part before .png is the col index
            except ValueError:
                print(f"Skipping file with unexpected format: {filename}")
                continue

            image_path = os.path.join(image_directory, filename)
            image = Image.open(image_path)

            # Preprocess the image
            image = preprocessor.preprocess(image)

            text = pytesseract.image_to_string(image, config='--psm 6 -c preserve_interword_spaces=1')

            text = text.strip()
            text = text.replace('\n', ' ')
            text = ' '.join(text.split())

            if row_index not in table_data:
                table_data[row_index] = {}
            table_data[row_index][col_index] = text

    if table_data:
        max_columns = max(max(cols.keys()) for cols in table_data.values())
    else:
        print("No data found. Exiting.")
        return

    with open(output_csv, mode='w', newline='') as file:
        writer = csv.writer(file)
        for row_index in sorted(table_data.keys()):
            row = []
            for col_index in range(max_columns + 1):
                cell_text = table_data[row_index].get(col_index, "")
                row.append(cell_text)
            writer.writerow(row)
