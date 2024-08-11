import os
import sys
import unittest
import tracemalloc
import warnings
from PIL import Image, ImageDraw
from pdf_to_image import pdf_to_images, enhance_image

sys.path.append('..')

class TestPDFToImages(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        """Set up the test environment once for all tests."""
        tracemalloc.start()
        warnings.simplefilter("ignore", ResourceWarning)

        cls.test_pdf_dir = r'C:\Users\olive\OneDrive\Desktop\CompSci\2024_semester_2\cits3200\ProfComp3200_38Project\Examples'
        cls.output_dir = 'test_images'
        cls.test_pdfs = []

        for filename in os.listdir(cls.test_pdf_dir):
            if filename.endswith('.pdf'):
                pdf_path = os.path.join(cls.test_pdf_dir, filename)
                cls.test_pdfs.append(pdf_path)

        os.makedirs(cls.output_dir, exist_ok=True)

    @classmethod
    def tearDownClass(cls):
        """Clean up after all tests and display memory usage."""
        if os.path.exists(cls.output_dir):
            for file in os.listdir(cls.output_dir):
                os.remove(os.path.join(cls.output_dir, file))
            os.rmdir(cls.output_dir)

        current, peak = tracemalloc.get_traced_memory()
        print(f"Current memory usage is {current / 10**6:.1f}MB; Peak was {peak / 10**6:.1f}MB")
        tracemalloc.stop()

    def test_pdf_to_images(self):
        """Test that the pdf_to_images function correctly converts each PDF to images."""
        for pdf_path in self.test_pdfs:
            with self.subTest(pdf=pdf_path):
                images = pdf_to_images(pdf_path)
                self.assertIsInstance(images, list)
                self.assertGreater(len(images), 0)

                for image in images:
                    self.assertIsInstance(image, Image.Image)

    def test_enhance_image(self):
        """Test that the enhance_image function correctly enhances an image."""
        for pdf_path in self.test_pdfs:
            with self.subTest(pdf=pdf_path):
                images = pdf_to_images(pdf_path)
                original_image = images[0]
                enhanced_image = enhance_image(original_image)

                self.assertIsInstance(enhanced_image, Image.Image)
                self.assertNotEqual(original_image.tobytes(), enhanced_image.tobytes())

    def test_output_image_saving(self):
        """Test saving the output images to ensure the conversion works."""
        for pdf_path in self.test_pdfs:
            with self.subTest(pdf=pdf_path):
                images = pdf_to_images(pdf_path)
                for i, image in enumerate(images):
                    image_path = os.path.join(self.output_dir, f'test_image_{i}.png')
                    with image:
                        image.save(image_path)
                    with Image.open(image_path) as saved_image:
                        self.assertTrue(os.path.exists(image_path))
                        self.assertEqual(image.size, saved_image.size)

if __name__ == '__main__':
    unittest.main()
