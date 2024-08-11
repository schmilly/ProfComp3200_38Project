Modules and Functions

    ExportTrOCR.py
        Handles OCR using the TrOCR model from Hugging Face.
        Functions for processing directories, image preprocessing, and text extraction.
        Customizations to suppress warnings and ensure accurate text extraction.

    image_preprocessor.py
        Initially included a complex ImagePreprocessor class for contrast, sharpness, resizing, and thresholding.
        Simplified to a basic enhance_image function for contrast, sharpness, and noise reduction to optimize images for OCR.

    pdf_to_image.py
        Converts PDFs into images using the pdf2image library.
        Applies image enhancements (contrast, sharpness, noise reduction) during conversion to prepare images for OCR.

Unit Tests

    TestOCRToCSV.py
        Validates OCR processing and CSV output.
        Tests various scenarios: different image formats, CSV correctness, and performance on large images.
        Optimized to process specific files for efficiency.

    TestImagePreprocessor.py
        Tests the ImagePreprocessor class and enhance_image function.
        Compares original and processed images to verify effective preprocessing for OCR.

    TestPDFToImages.py
        Ensures correct PDF-to-image conversion and enhancement.
        Tests efficiency across multiple PDFs and verifies image enhancement during conversion.