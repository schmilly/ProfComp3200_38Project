import os
import sys
import csv
import shutil
import random
import string
import unittest
from PIL import Image, ImageDraw, ImageFont

sys.path.append('..')

from OCRExportPaddle import perform_paddle_ocr, preprocess_image

class TestOCRToCSV(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        """Set up the test environment once for all tests."""
        cls.source_dir = r'C:\Users\olive\OneDrive\Desktop\CompSci\2024_semester_2\cits3200\ProfComp3200_38Project\Code\unitTests\Cellularised-Example'
        cls.test_dir = 'test_images'
        cls.output_csv = 'test_output.csv'
        os.makedirs(cls.test_dir, exist_ok=True)

        copied_files = []
        for filename in os.listdir(cls.source_dir):
            if filename.endswith('.png'):
                source_file = os.path.join(cls.source_dir, filename)
                dest_file = os.path.join(cls.test_dir, filename)
                shutil.copy(source_file, dest_file)
                copied_files.append(filename)
                image = Image.open(dest_file)
                preprocessed_image = preprocess_image(image)
                preprocessed_image.save(dest_file)

        print(f"Copied and preprocessed files: {copied_files}")

    @classmethod
    def tearDownClass(cls):
        """Clean up after all tests."""
        for file in os.listdir(cls.test_dir):
            os.remove(os.path.join(cls.test_dir, file))
        os.rmdir(cls.test_dir)
        if os.path.exists(cls.output_csv):
            os.remove(cls.output_csv)

    def create_test_image(self, filename, text):
        image = Image.new('RGB', (200, 50), color=(255, 255, 255))
        d = ImageDraw.Draw(image)
        try:
            font = ImageFont.truetype("arial.ttf", 20)
        except IOError:
            font = ImageFont.load_default()
        d.text((10, 10), text, font=font, fill=(0, 0, 0))
        image.save(os.path.join(self.test_dir, filename))

    def run_main_function(self, specific_files=None):
        """Helper function to run the main OCR function on specific files or all files if none are specified."""
        table_data = {}

        files_to_process = specific_files if specific_files else os.listdir(self.test_dir)

        for filename in files_to_process:
            if filename.endswith(".png"):
                row_index = len(table_data)
                col_index = 0
                image_path = os.path.join(self.test_dir, filename)
                image = Image.open(image_path)
                image = preprocess_image(image)
                text = perform_paddle_ocr(image)

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

    def test_ocr_processing(self):
        """Test that OCR processes images correctly."""
        specific_files = [
            'page_iiicgko_0_0.png',
            'page_iiicgko_0_1.png',
            'page_iiicgko_0_2.png',
            'page_iiicgko_0_3.png',
            'page_iiicgko_0_4.png',
            'page_iiicgko_1_0.png',
            'page_iiicgko_1_1.png',
            'page_iiicgko_1_2.png',
            'page_iiicgko_1_3.png',
            'page_iiicgko_1_4.png'
        ]
        self.run_main_function(specific_files=specific_files)

        with open(self.output_csv, newline='') as csvfile:
            reader = csv.reader(csvfile)
            rows = list(reader)

        expected_rows = [
            ['Geschlecht', 'Wien', 'Sonstiges Nieder- Oesterreich', 'Nieder- Oesterreich iiberhampt', 'Ober- Oesterreich'],
            ['m.', '291.183', '70.739', '361.922', '10.010']
        ]

        self.assertEqual(len(rows), len(expected_rows))
        for i in range(len(rows)):
            self.assertEqual(rows[i], expected_rows[i])

    def test_empty_columns_handled(self):
        """Test that missing columns are handled correctly."""
        random_string = ''.join(random.choices(string.ascii_letters + string.digits + string.punctuation, k=15))
        self.create_test_image('test_2_0.png', f'Only one text {random_string}')
        self.run_main_function(specific_files=['test_2_0.png'])

        with open(self.output_csv, newline='') as csvfile:
            reader = csv.reader(csvfile)
            rows = list(reader)

        expected_rows = [[f'Only one text {random_string}']]
        self.assertEqual(len(rows), len(expected_rows))
        for i in range(len(rows)):
            self.assertEqual(rows[i], expected_rows[i])

    def test_output_format(self):
        """Test that the output CSV is in the correct format."""
        self.run_main_function()

        with open(self.output_csv, newline='') as csvfile:
            reader = csv.reader(csvfile)
            rows = list(reader)

        for row in rows:
            for cell in row:
                self.assertIsInstance(cell, str)

    def test_invalid_image_extension(self):
        """Test that non-png files are ignored."""
        random_string = ''.join(random.choices(string.ascii_letters + string.digits + string.punctuation, k=15))
        self.create_test_image('test_invalid.jpg', f'This should not be processed {random_string}')
        self.run_main_function(specific_files=['test_invalid.jpg'])

        with open(self.output_csv, newline='') as csvfile:
            reader = csv.reader(csvfile)
            rows = list(reader)

        expected_rows = []
        self.assertEqual(len(rows), len(expected_rows))

    def test_special_characters(self):
        """Test that special characters in images are handled correctly."""
        random_string = ''.join(random.choices(string.ascii_letters + string.digits + string.punctuation, k=15))
        self.create_test_image('test_special_0_0.png', f'Spécial €haracters @ {random_string}')
        self.run_main_function(specific_files=['test_special_0_0.png'])

        with open(self.output_csv, newline='') as csvfile:
            reader = csv.reader(csvfile)
            rows = list(reader)

        expected_rows = [[f'Spécial €haracters @ {random_string}']]
        self.assertEqual(len(rows), len(expected_rows))
        for i in range(len(rows)):
            self.assertEqual(rows[i], expected_rows[i])

    def test_large_image(self):
        """Test that OCR can handle large images with large text."""
        random_string = ''.join(random.choices(string.ascii_letters + string.digits + string.punctuation, k=15))
        image = Image.new('RGB', (4000, 1000), color=(255, 255, 255))
        d = ImageDraw.Draw(image)
        try:
            font = ImageFont.truetype("arial.ttf", 150)
        except IOError:
            font = ImageFont.load_default()

        text = f'This is a large image test with {random_string}'
        d.text((300, 600), text, fill=(0, 0, 0), font=font)
        large_image_path = os.path.join(self.test_dir, 'test_large_0_0.png')
        image.save(large_image_path)

        self.run_main_function(specific_files=['test_large_0_0.png'])

        with open(self.output_csv, newline='') as csvfile:
            reader = csv.reader(csvfile)
            rows = list(reader)

        expected_rows = [[text]]
        self.assertEqual(len(rows), len(expected_rows))
        for i in range(len(rows)):
            self.assertEqual(rows[i], expected_rows[i])

    def test_ocr_performance(self):
        """Test the performance of the OCR system with multiple images."""
        random_strings = []
        specific_files = []
        for i in range(10):
            random_string = ''.join(random.choices(string.ascii_letters + string.digits + string.punctuation, k=15))
            random_strings.append(random_string)
            filename = f'test_multi_{i}_0.png'
            self.create_test_image(filename, f'Test text {random_string}')
            specific_files.append(filename)

        self.run_main_function(specific_files=specific_files)

        with open(self.output_csv, newline='') as csvfile:
            reader = csv.reader(csvfile)
            rows = list(reader)

        expected_rows = [[f'Test text {random_strings[i]}'] for i in range(10)]
        self.assertEqual(len(rows), len(expected_rows))
        for i in range(len(rows)):
            self.assertEqual(rows[i], expected_rows[i])

    def test_empty_image(self):
        """Test that OCR handles empty images without text."""
        image = Image.new('RGB', (200, 50), color=(255, 255, 255))
        empty_image_path = os.path.join(self.test_dir, 'test_empty_0_0.png')
        image.save(empty_image_path)

        self.run_main_function(specific_files=['test_empty_0_0.png'])

        with open(self.output_csv, newline='') as csvfile:
            reader = csv.reader(csvfile)
            rows = list(reader)

        expected_rows = [['']]
        self.assertEqual(len(rows), len(expected_rows))
        for i in range(len(rows)):
            self.assertEqual(rows[i], expected_rows[i])

    def test_multiple_columns(self):
        """Test that OCR handles multiple columns correctly."""
        random_string = ''.join(random.choices(string.ascii_letters + string.digits + string.punctuation, k=15))
        image = Image.new('RGB', (400, 50), color=(255, 255, 255))
        d = ImageDraw.Draw(image)
        d.text((10, 10), f'Column 1 {random_string}', fill=(0, 0, 0))
        d.text((210, 10), f'Column 2 {random_string}', fill=(0, 0, 0))
        multiple_columns_image_path = os.path.join(self.test_dir, 'test_columns_0_0.png')
        image.save(multiple_columns_image_path)

        self.run_main_function(specific_files=['test_columns_0_0.png'])

        with open(self.output_csv, newline='') as csvfile:
            reader = csv.reader(csvfile)
            rows = list(reader)

        expected_rows = [[f'Column 1 {random_string}', f'Column 2 {random_string}']]
        self.assertEqual(len(rows), len(expected_rows))
        for i in range(len(rows)):
            self.assertEqual(rows[i], expected_rows[i])

    def test_noisy_background(self):
        """Test that OCR can handle images with noisy backgrounds."""
        random_string = ''.join(random.choices(string.ascii_letters + string.digits + string.punctuation, k=15))
        image = Image.new('RGB', (400, 50), color=(0, 0, 0))
        d = ImageDraw.Draw(image)
        d.text((10, 10), f'Noisy Background {random_string}', fill=(255, 255, 255))
        
        # Add noise
        for _ in range(1000):
            x = random.randint(0, 399)
            y = random.randint(0, 49)
            image.putpixel((x, y), (random.randint(0, 255), random.randint(0, 255), random.randint(0, 255)))
        
        noisy_image_path = os.path.join(self.test_dir, 'test_noisy_0_0.png')
        image.save(noisy_image_path)

        self.run_main_function(specific_files=['test_noisy_0_0.png'])

        with open(self.output_csv, newline='') as csvfile:
            reader = csv.reader(csvfile)
            rows = list(reader)

        expected_rows = [[f'Noisy Background {random_string}']]
        self.assertEqual(len(rows), len(expected_rows))
        for i in range(len(rows)):
            self.assertEqual(rows[i], expected_rows[i])

    def test_skewed_text(self):
        """Test that OCR can handle skewed text correctly."""
        random_string = ''.join(random.choices(string.ascii_letters + string.digits + string.punctuation, k=15))
        image = Image.new('RGB', (400, 50), color=(255, 255, 255))
        d = ImageDraw.Draw(image)
        try:
            font = ImageFont.truetype("arial.ttf", 20)
        except IOError:
            font = ImageFont.load_default()
        
        text = f"Skewed Text {random_string}"
        d.text((10, 10), text, font=font, fill=(0, 0, 0))

        # Apply skew transformation
        image = image.rotate(15, expand=1)
        skewed_image_path = os.path.join(self.test_dir, 'test_skewed_0_0.png')
        image.save(skewed_image_path)

        self.run_main_function(specific_files=['test_skewed_0_0.png'])

        with open(self.output_csv, newline='') as csvfile:
            reader = csv.reader(csvfile)
            rows = list(reader)

        expected_rows = [[text]]
        self.assertEqual(len(rows), len(expected_rows))
        for i in range(len(rows)):
            self.assertEqual(rows[i], expected_rows[i])

    def test_varying_font_sizes(self):
        """Test that OCR handles varying font sizes correctly."""
        random_string = ''.join(random.choices(string.ascii_letters + string.digits + string.punctuation, k=15))
        image = Image.new('RGB', (400, 200), color=(255, 255, 255))
        d = ImageDraw.Draw(image)
        
        try:
            font_large = ImageFont.truetype("arial.ttf", 40)
            font_medium = ImageFont.truetype("arial.ttf", 20)
            font_small = ImageFont.truetype("arial.ttf", 10)
        except IOError:
            font_large = ImageFont.load_default()
            font_medium = ImageFont.load_default()
            font_small = ImageFont.load_default()

        d.text((10, 10), f'Large Text {random_string}', font=font_large, fill=(0, 0, 0))
        d.text((10, 60), f'Medium Text {random_string}', font=font_medium, fill=(0, 0, 0))
        d.text((10, 100), f'Small Text {random_string}', font=font_small, fill=(0, 0, 0))
        
        varying_font_path = os.path.join(self.test_dir, 'test_varying_font_0_0.png')
        image.save(varying_font_path)

        self.run_main_function(specific_files=['test_varying_font_0_0.png'])

        with open(self.output_csv, newline='') as csvfile:
            reader = csv.reader(csvfile)
            rows = list(reader)

        expected_rows = [[f'Large Text {random_string}', f'Medium Text {random_string}', f'Small Text {random_string}']]
        self.assertEqual(len(rows), len(expected_rows))
        for i in range(len(rows)):
            self.assertEqual(rows[i], expected_rows[i])

    def test_low_contrast_text(self):
        """Test that OCR can handle low contrast text."""
        random_string = ''.join(random.choices(string.ascii_letters + string.digits + string.punctuation, k=15))
        image = Image.new('RGB', (400, 50), color=(200, 200, 200))
        d = ImageDraw.Draw(image)
        try:
            font = ImageFont.truetype("arial.ttf", 20)
        except IOError:
            font = ImageFont.load_default()
        
        d.text((10, 10), f'Low Contrast {random_string}', font=font, fill=(180, 180, 180))
        
        low_contrast_path = os.path.join(self.test_dir, 'test_low_contrast_0_0.png')
        image.save(low_contrast_path)

        self.run_main_function(specific_files=['test_low_contrast_0_0.png'])

        with open(self.output_csv, newline='') as csvfile:
            reader = csv.reader(csvfile)
            rows = list(reader)

        expected_rows = [[f'Low Contrast {random_string}']]
        self.assertEqual(len(rows), len(expected_rows))
        for i in range(len(rows)):
            self.assertEqual(rows[i], expected_rows[i])


    def test_mixed_languages(self):
        """Test that OCR can handle mixed language text, with each sentence in an individual image."""
        
        # Allow full diff to be shown
        self.maxDiff = None

        # Define the sentences in different languages
        sentences = {
            "English": "The quick brown fox jumps over the lazy dog",
            "Mandarin": "敏捷的棕色狐狸跳过了懒狗",
            "Hindi": "तेज़ भूरी लोमड़ी आलसी कुत्ते के ऊपर कूदती है",
            "Spanish": "El rápido zorro marrón salta sobre el perro perezoso",
            "French": "Le renard brun rapide saute par-dessus le chien paresseux",
            "Arabic": "الثعلب البني السريع يقفز فوق الكلب الكسول",
            "Bengali": "দ্রুত বাদামী শিয়াল অলস কুকুরের উপর ঝাঁপিয়ে পড়ে",
            "Russian": "Быстрая коричневая лиса прыгает через ленивую собаку",
            "Portuguese": "A rápida raposa marrom pula sobre o cachorro preguiçoso",
            "Urdu": "تیز بھورا لومڑ سست کتے کے اوپر چھلانگ لگا دیتا ہے",
            "Indonesian": "Rubah coklat yang cepat melompati anjing yang malas",
        }

        # Path to the Noto Sans font that supports multiple languages
        font_path = r"C:\Users\olive\Downloads\Noto_Sans\NotoSans-VariableFont_wdth,wght.ttf"

        for language, sentence in sentences.items():
            filename = f'test_{language.lower()}_0_0.png'
            image = Image.new('RGB', (2000, 500), color=(255, 255, 255))
            d = ImageDraw.Draw(image)
            try:
                font = ImageFont.truetype(font_path, 40)
            except IOError:
                font = ImageFont.load_default()
            d.text((10, 25), sentence, font=font, fill=(0, 0, 0))
            image.save(os.path.join(self.test_dir, filename))

        # Run OCR on each image and check the results
        ocr_output = []
        for language, sentence in sentences.items():
            filename = f'test_{language.lower()}_0_0.png'
            self.run_main_function(specific_files=[filename])
            with open(self.output_csv, newline='') as csvfile:
                reader = csv.reader(csvfile)
                rows = list(reader)
            ocr_output.append(' '.join(' '.join(row) for row in rows).strip())

        # Compare the OCR output with the expected output
        expected_output = list(sentences.values())
        print("\nExpected Output:\n", expected_output)
        print("\nOCR Output:\n", ocr_output)

        self.assertEqual(ocr_output, expected_output)

if __name__ == '__main__':
    unittest.main()
