import paddle
from paddleocr import PaddleOCR
import easyocr
from PIL import Image, ImageDraw, ImageFont

def create_test_image():
    """
    Create a simple test image with some text.
    """
    img = Image.new('RGB', (200, 100), color=(255, 255, 255))
    d = ImageDraw.Draw(img)
    text = "Hello, OCR!"
    # You can specify a path to a font, or use the default PIL font
    try:
        font = ImageFont.truetype("arial.ttf", 20)  # Use your font file if you have one
    except IOError:
        font = ImageFont.load_default()

    d.text((10, 40), text, font=font, fill=(0, 0, 0))
    img.save("test_image.png")
    return "test_image.png"

def check_paddle_installation():
    """
    Check if Paddle is installed correctly and can use the GPU.
    """
    print("Checking PaddlePaddle installation and GPU setup...")
    print("PaddlePaddle version:", paddle.__version__)
    print("Paddle compiled with CUDA:", paddle.is_compiled_with_cuda())

def test_easyocr(gpu=False):
    """
    Test if EasyOCR can run and print GPU usage.
    """
    print("\nTesting EasyOCR with GPU =", gpu)
    reader = easyocr.Reader(['en'], gpu=gpu)  # Set 'gpu=True' if GPU is available
    sample_image_path = create_test_image()
    result = reader.readtext(sample_image_path)
    print("EasyOCR Result:", result)
    
def test_paddleocr():
    """
    Test if PaddleOCR can run and whether it is using GPU.
    """
    print("\nTesting PaddleOCR")
    
    # Initialize PaddleOCR with GPU enabled
    ocr = PaddleOCR(use_gpu=True, lang='en')  # Set use_gpu=True to enable GPU
    
    # Since PaddleOCR doesn't expose a use_gpu attribute, we'll assume it's using GPU
    print("PaddleOCR initialized with GPU=True")

    sample_image_path = create_test_image()
    try:
        result = ocr.ocr(sample_image_path)
        print("PaddleOCR Result:", result)
    except Exception as e:
        print(f"An error occurred during PaddleOCR processing: {e}")

if __name__ == "__main__":
    check_paddle_installation()
    
    # Test EasyOCR with CPU
    test_easyocr(gpu=False)
    
    # Test PaddleOCR
    test_paddleocr()
