import unittest
import os
from PIL import Image, ImageChops
from image_preprocessor import ImagePreprocessor

class TestImagePreprocessor(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        """Set up the test environment."""
        cls.image_path = r'C:\Users\olive\OneDrive\Desktop\CompSci\2024_semester_2\cits3200\ProfComp3200_38Project\Code\unitTests\PageExport.png' 
        cls.original_image = Image.open(cls.image_path)
        cls.preprocessor = ImagePreprocessor(contrast=2.0, sharpness=2.0, resize_factor=1.0, thresholding=True) 
        cls.output_dir = 'ImageDifference' 

        # Create the directory if it doesn't exist, or clear it if it does
        if not os.path.exists(cls.output_dir):
            os.makedirs(cls.output_dir)
        else:
            for file in os.listdir(cls.output_dir):
                file_path = os.path.join(cls.output_dir, file)
                if os.path.isfile(file_path):
                    os.remove(file_path)

    def test_preprocessing(self):
        """Test that the image preprocessing works and save the processed images for inspection."""
        processed_image = self.preprocessor.preprocess(self.original_image)

        # Calculate the difference between the original and processed images
        difference = ImageChops.difference(self.original_image.convert("RGB"), processed_image)

        # Save the original, processed, and difference images to the specified directory
        self.original_image.save(os.path.join(self.output_dir, 'original_image.png'))
        processed_image.save(os.path.join(self.output_dir, 'processed_image.png'))
        difference.save(os.path.join(self.output_dir, 'difference_image.png'))

        # Check if the processed image is different from the original
        self.assertFalse(difference.getbbox() is None, "The processed image should be different from the original image.")

if __name__ == '__main__':
    unittest.main()
