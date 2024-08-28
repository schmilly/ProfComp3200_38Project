import unittest
import os
import csv
import sys
from PIL import Image, ImageDraw
import shutil

# Ensure the path includes the directories for the modules
sys.path.append('..')

from ExportTrOCR import trocr_ocr
from image_preprocessor import ImagePreprocessor

class TestOCRToCSV(unittest.TestCase):

    def setUp(self):
        """Set up the test environment"""
        # Specify the directory to scan for test images
        self.source_dir = r'C:\Users\olive\OneDrive\Desktop\CompSci\2024_semester_2\cits3200\ProfComp3200_38Project\Examples\Cellularised-Example'
        self.test_dir = 'test_images'
        self.output_csv = 'test_output.csv'

        # Initialize the ImagePreprocessor
        self.preprocessor = ImagePreprocessor(contrast=3, sharpness=2)

        # Create a temporary directory to copy the test images into
        os.makedirs(self.test_dir, exist_ok=True)

        # Copy and preprocess all PNG images from the source directory to the test directory
        copied_files = []
        for filename in os.listdir(self.source_dir):
            if filename.endswith('.png'):
                source_file = os.path.join(self.source_dir, filename)
                dest_file = os.path.join(self.test_dir, filename)

                # Copy the image
                shutil.copy(source_file, dest_file)
                copied_files.append(filename)

                # Open the copied image and preprocess it
                image = Image.open(dest_file)
                preprocessed_image = self.preprocessor.preprocess(image)

                # Save the preprocessed image back to the temporary directory
                preprocessed_image.save(dest_file)

        # Print out the files that were copied and preprocessed for debugging purposes
        print(f"Copied and preprocessed files: {copied_files}")

    def tearDown(self):
        """Clean up after the test"""
        # Remove test images and output CSV
        for file in os.listdir(self.test_dir):
            os.remove(os.path.join(self.test_dir, file))
        os.rmdir(self.test_dir)

        if os.path.exists(self.output_csv):
            os.remove(self.output_csv)

    def create_test_image(self, filename, text):
        """Helper function to create a test image with text"""
        image = Image.new('RGB', (200, 50), color = (255, 255, 255))
        d = ImageDraw.Draw(image)
        d.text((10, 10), text, fill=(0, 0, 0))
        image.save(os.path.join(self.test_dir, filename))

    def test_ocr_processing(self):
        """Test that OCR processes images correctly"""
        self.run_main_function()

        # Verify the content of the CSV
        with open(self.output_csv, newline='') as csvfile:
            reader = csv.reader(csvfile)
            rows = list(reader)

        # Expected output
        expected_rows = [
            ['Geschlecht', 'Wien', 'Sonstiges Nieder- Oesterreich', 'Nieder- Oesterreich iiberhampt', 'Ober- Oesterreich'],
            ['m.', '291.183', '70.739', '361.922', '10.010']
        ]

        self.assertEqual(len(rows), len(expected_rows))  # We expect 2 rows
        for i in range(len(rows)):
            self.assertEqual(rows[i], expected_rows[i])

    def test_empty_columns_handled(self):
        """Test that missing columns are handled correctly"""
        # Create a test case where there are missing columns
        self.create_test_image('test_2_0.png', 'Only one text')

        self.run_main_function()

        # Verify the content of the CSV
        with open(self.output_csv, newline='') as csvfile:
            reader = csv.reader(csvfile)
            rows = list(reader)

        # Expected output should include handling of empty columns
        expected_rows = [
            ['Geschlecht', 'Wien', 'Sonstiges Nieder- Oesterreich', 'Nieder- Oesterreich iiberhampt', 'Ober- Oesterreich'],
            ['m.', '291.183', '70.739', '361.922', '10.010'],
            ['Only one text', '', '', '', '']
        ]

        self.assertEqual(len(rows), len(expected_rows))  # We expect 3 rows
        for i in range(len(rows)):
            self.assertEqual(rows[i], expected_rows[i])

    def test_output_format(self):
        """Test that the output CSV is in the correct format"""
        self.run_main_function()

        # Verify that the CSV has correct headers and no extra delimiters
        with open(self.output_csv, newline='') as csvfile:
            reader = csv.reader(csvfile)
            rows = list(reader)

        for row in rows:
            for cell in row:
                self.assertIsInstance(cell, str)  # All cells should contain strings

    def test_invalid_image_extension(self):
        """Test that non-png files are ignored"""
        self.create_test_image('test_invalid.jpg', 'This should not be processed')

        self.run_main_function()

        with open(self.output_csv, newline='') as csvfile:
            reader = csv.reader(csvfile)
            rows = list(reader)

        # Since only PNG files are processed, the content should be as expected
        expected_rows = [
            ['Geschlecht', 'Wien', 'Sonstiges Nieder- Oesterreich', 'Nieder- Oesterreich iiberhampt', 'Ober- Oesterreich'],
            ['m.', '291.183', '70.739', '361.922', '10.010']
        ]

        self.assertEqual(len(rows), len(expected_rows))
        for i in range(len(rows)):
            self.assertEqual(rows[i], expected_rows[i])

    def run_main_function(self):
        """Helper function to run the main OCR function"""
        table_data = {}
        preprocessor = ImagePreprocessor(contrast=3, sharpness=2)  # Initialize the ImagePreprocessor

        for filename in os.listdir(self.test_dir):
            if filename.endswith(".png"):
                parts = filename.split('_')

                # Assuming the format: page_iiicgko_row_col.png
                try:
                    row_index = int(parts[-2])  # The second last part is the row index
                    col_index = int(parts[-1].split('.')[0])  # The last part before .png is the col index
                except ValueError:
                    print(f"Skipping file with unexpected format: {filename}")
                    continue

                image_path = os.path.join(self.test_dir, filename)
                image = Image.open(image_path)

                # Preprocess the image
                image = preprocessor.preprocess(image)

                # Use the trocr_ocr function to extract text from the preprocessed image
                text = trocr_ocr(image)

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

        with open(self.output_csv, mode='w', newline='') as file:
            writer = csv.writer(file)
            for row_index in sorted(table_data.keys()):
                row = []
                for col_index in range(max_columns + 1):
                    cell_text = table_data[row_index].get(col_index, "")
                    row.append(cell_text)
                writer.writerow(row)


if __name__ == '__main__':
    unittest.main()
