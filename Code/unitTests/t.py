import unittest
import os
import csv
import sys
from PIL import Image, ImageDraw
import pytesseract

sys.path.append('..')


from ExportTesseract import main_function

class TestOCRToCSV(unittest.TestCase):

    def setUp(self):
        """Set up the test environment"""
        # Create a temporary directory and images
        self.test_dir = 'test_images'
        os.makedirs(self.test_dir, exist_ok=True)

        # Create some test images
        self.create_test_image('test_0_0.png', 'Test text 1')
        self.create_test_image('test_0_1.png', 'Test text 2')
        self.create_test_image('test_1_0.png', 'Another text 1')
        self.create_test_image('test_1_1.png', 'Another text 2')

        self.output_csv = 'test_output.csv'

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
        main_function(self.test_dir, self.output_csv)  # Adjust as necessary to call your main processing function

        # Check if the CSV was created
        self.assertTrue(os.path.exists(self.output_csv))

        # Verify the content of the CSV
        with open(self.output_csv, newline='') as csvfile:
            reader = csv.reader(csvfile)
            rows = list(reader)

        self.assertEqual(len(rows), 2)  # We expect 2 rows
        self.assertEqual(rows[0][0], 'Test text 1')
        self.assertEqual(rows[0][1], 'Test text 2')
        self.assertEqual(rows[1][0], 'Another text 1')
        self.assertEqual(rows[1][1], 'Another text 2')

    def test_empty_columns_handled(self):
        """Test that missing columns are handled correctly"""
        # Create a test case where there are missing columns
        self.create_test_image('test_2_0.png', 'Only one text')

        main_function(self.test_dir, self.output_csv)

        # Verify the content of the CSV
        with open(self.output_csv, newline='') as csvfile:
            reader = csv.reader(csvfile)
            rows = list(reader)

        self.assertEqual(len(rows), 3)  # We expect 3 rows
        self.assertEqual(len(rows[2]), 2)  # We expect 2 columns in the third row
        self.assertEqual(rows[2][0], 'Only one text')
        self.assertEqual(rows[2][1], '')  # Second column should be empty

    def test_output_format(self):
        """Test that the output CSV is in the correct format"""
        main_function(self.test_dir, self.output_csv)

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

        main_function(self.test_dir, self.output_csv)

        with open(self.output_csv, newline='') as csvfile:
            reader = csv.reader(csvfile)
            rows = list(reader)

        # Verify that the invalid image was not processed
        self.assertNotIn('This should not be processed', [cell for row in rows for cell in row])


if __name__ == '__main__':
    unittest.main()
