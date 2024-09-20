import os
import time
import logging
import csv
from pathlib import Path
from shash_code import *
from TableDetectionTests import *
from Cellularize import *
from OCRCompare import *
from paddleocr import PaddleOCR
from PIL import Image, ImageEnhance, ImageFilter
import easyocr
import paddle
import cv2
import numpy as np
from tqdm import tqdm

# Set logging level to WARNING to reduce verbosity
for logger_name in logging.root.manager.loggerDict:
    logging.getLogger(logger_name).setLevel(logging.WARNING)

def preprocess_image(image):
    """Apply preprocessing to enhance OCR accuracy."""
    image = image.convert('L')  # Convert to grayscale
    base_width = image.width * 2
    base_height = image.height * 2
    image = image.resize((base_width, base_height), Image.LANCZOS)

    # Enhance sharpness and contrast
    enhancer = ImageEnhance.Sharpness(image)
    image = enhancer.enhance(2)
    enhancer = ImageEnhance.Contrast(image)
    image = enhancer.enhance(4)

    # Denoise image
    image = image.filter(ImageFilter.MedianFilter(size=3))

    return image.convert('RGB')

def perform_paddle_ocr(image, ocr_engine, return_confidence=False):
    """Perform OCR using PaddleOCR."""
    image_array = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
    try:
        result = ocr_engine.ocr(image_array, cls=True)
        if not result:
            return ('', 0) if return_confidence else ''
        texts = []
        confidences = []
        for line in result:
            if line:
                for info in line:
                    text = info[1][0]
                    confidence = info[1][1]
                    texts.append(text)
                    confidences.append(confidence)
        combined_text = ' '.join(texts)
        average_confidence = sum(confidences) / len(confidences) if confidences else 0
        return (combined_text, average_confidence) if return_confidence else combined_text
    except Exception as e:
        print(f"An error occurred during PaddleOCR processing: {e}")
        return ('', 0) if return_confidence else ''

def perform_easyocr(image, reader):
    """Perform OCR using EasyOCR."""
    results = reader.readtext(np.array(image), detail=1, paragraph=False)
    texts = [res[1] for res in results]
    confidences = [res[2] for res in results if res[2] > 0]  # Filter zero confidence

    if confidences:
        average_confidence = sum(confidences) / len(confidences)
        full_text = ' '.join(texts)
        return full_text, average_confidence
    else:
        return '', 0

def process_image(filename):
    """Process a single image and perform OCR."""
    # Extract row and column indices from filename
    parts = filename.split('_')
    try:
        row_index = int(parts[2])
        col_index = int(parts[3].split('.')[0])
    except (IndexError, ValueError) as e:
        print(f"Error parsing filename {filename}: {e}")
        return None

    image = Image.open(filename).convert("RGB")
    processed_image = preprocess_image(image)
    
    # Perform OCR on the processed image first
    processed_text, processed_confidence = perform_paddle_ocr(processed_image, ocr, return_confidence=True)
    
    if processed_confidence >= 0.98:
        best_text = processed_text
        best_confidence = processed_confidence
        source = 'Processed Image, PaddleOCR'
    else:
        # Try OCR on the original image
        original_text, original_confidence = perform_paddle_ocr(image, ocr, return_confidence=True)
        
        if original_confidence >= 0.8:
            best_text = original_text
            best_confidence = original_confidence
            source = 'Original Image, PaddleOCR'
        else:
            # Use EasyOCR if confidence is still low
            easy_processed_text, easy_processed_conf = perform_easyocr(processed_image, reader)
            easy_original_text, easy_original_conf = perform_easyocr(image, reader)
            
            results = [
                (processed_text, processed_confidence, 'Processed Image, PaddleOCR'),
                (original_text, original_confidence, 'Original Image, PaddleOCR'),
                (easy_processed_text, easy_processed_conf, 'Processed Image, EasyOCR'),
                (easy_original_text, easy_original_conf, 'Original Image, EasyOCR')
            ]
            
            best_text, best_confidence, source = max(results, key=lambda x: x[1])
    
    if best_confidence == 0:
        return None
    
    return (row_index, col_index, best_text, best_confidence, source, filename)

def main():
    start_time = time.time()

    storedir = "temp"
    if not os.path.exists(storedir):
        os.makedirs(storedir)

    pdf_file = Path("..") / "Examples" / "2Page_AUSTRIA_1890_T2_g0bp.pdf"
    if not pdf_file.exists():
        raise FileNotFoundError(f"PDF file not found: {pdf_file.resolve()}")

    # Convert PDF to images
    image_list = []
    counter = 0
    page_num = 0
    for i in pdf_to_image.pdf_to_images(str(pdf_file)):
        name = os.path.join(storedir, f"Document_{counter}.png")
        i.save(name)
        image_list.append(os.path.join(str(Path.cwd()), name))
        counter += 1

    # Detect tables and cellularize
    TableMap = []
    for filepath in image_list:
        TableCoords = luminositybased.findTable(filepath, "borderless", "borderless")
        FormattedCoords = [luminositybased.convert_to_pairs(CordList) for CordList in TableCoords]
        TableMap.append(FormattedCoords)

    locationlists = []
    for index, Table in enumerate(TableMap):
        locationlists.append(cellularize_Page_colrow(image_list[index], Table[1], Table[0], page_num + index))

    output_csv = 'output.csv'
    table_data = {}
    total = 0
    bad = 0
    easyocr_count = 0
    paddleocr_count = 0

    # Flatten the list of image filenames
    all_filenames = [filename for collection in locationlists for filename in collection]

    # Initialize OCR engines once in the main thread
    use_gpu = paddle.device.is_compiled_with_cuda()
    global ocr
    global reader
    ocr = PaddleOCR(
        use_angle_cls=True,
        lang='en',
        rec_model_dir='en_PP-OCRv4_rec',
        version='PP-OCRv4',
        det_db_thresh=0.35,
        det_db_box_thresh=0.45,
        det_db_unclip_ratio=1.8,
        cls_thresh=0.95,
        use_space_char=True,
        rec_image_shape='3, 48, 320',
        det_limit_side_len=960,
        use_gpu=use_gpu
    )
    reader = easyocr.Reader(['en'], gpu=use_gpu)

    # Process images sequentially with a progress bar
    results = []
    for filename in tqdm(all_filenames, desc="Processing images"):
        result = process_image(filename)
        results.append(result)

    # Process the results
    for result in results:
        if result is None:
            continue
        row_index, col_index, best_text, best_confidence, source, filename = result

        if 'EasyOCR' in source:
            easyocr_count += 1
        else:
            paddleocr_count += 1

        total += 1

        if best_confidence < 0.8:
            bad += 1
            print(f"Review needed for {filename}: {best_text} (Confidence: {best_confidence}, Source: {source})")

        if row_index not in table_data:
            table_data[row_index] = {}
        table_data[row_index][col_index] = best_text

    # Write results to CSV
    max_columns = max(max(cols.keys()) for cols in table_data.values())
    with open(output_csv, mode='w', newline='') as file:
        writer = csv.writer(file)
        for row_index in sorted(table_data.keys()):
            row = [table_data[row_index].get(col_index, "") for col_index in range(max_columns + 1)]
            writer.writerow(row)

    if total > 0:
        print(f"Percentage less than 80% confidence score is {bad / total * 100:.2f}% with {bad} possibly wrong")
    else:
        print("No valid OCR results to calculate confidence percentage.")

    print("OCR verification complete. Results saved to CSV.")
    print(f"Results using EasyOCR: {easyocr_count}")
    print(f"Results using PaddleOCR: {paddleocr_count}")

    # Cleanup
    for file in os.listdir(storedir):
        file_path = os.path.join(storedir, file)
        try:
            os.remove(file_path)
        except Exception as e:
            print(f"Error deleting file {file_path}: {e}")

    try:
        os.rmdir(storedir)
    except Exception as e:
        print(f"Error removing directory {storedir}: {e}")

    end_time = time.time()
    elapsed_time = end_time - start_time
    print(f"Total execution time: {elapsed_time:.2f} seconds")

if __name__ == '__main__':
    main()
