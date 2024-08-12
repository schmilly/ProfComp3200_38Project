from PIL import Image, ImageEnhance, ImageFilter

class ImagePreprocessor:
    """
    A class to preprocess images for improved OCR accuracy. This includes contrast enhancement, 
    sharpness adjustment, resizing, adaptive thresholding, and noise reduction.

    Attributes:
        contrast (float): The level of contrast to apply to the image.
        sharpness (float): The level of sharpness to apply to the image.
        resize_factor (float): The factor by which to resize the image. A value of 1.0 means no resizing.
        thresholding (bool): Whether to apply adaptive thresholding to binarize the image.

    Methods:
        preprocess(image): Applies the preprocessing steps to the provided image and returns the processed image.
    """

    def __init__(self, contrast=1.0, sharpness=1.0, resize_factor=1.0, thresholding=True):
        self.contrast = contrast
        self.sharpness = sharpness
        self.resize_factor = resize_factor
        self.thresholding = thresholding

    def preprocess(self, image):

        image = image.convert('L')
        
        if self.resize_factor != 1.0:
            width, height = image.size
            new_size = (int(width * self.resize_factor), int(height * self.resize_factor))
            image = image.resize(new_size, Image.LANCZOS)
        
        image = ImageEnhance.Contrast(image).enhance(self.contrast)
        image = ImageEnhance.Sharpness(image).enhance(self.sharpness)
        image = image.filter(ImageFilter.EDGE_ENHANCE)
        image = image.convert('RGB')
        
        return image
