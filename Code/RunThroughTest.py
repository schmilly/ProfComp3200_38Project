# ocr_module 

import os
import time
import logging
import csv
from pathlib import Path
import pdf_to_image
from TableDetection import luminositybased
from Cellularize import cellularize_Page_colrow
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

def process_image(filename, ocr, reader):
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

def convert_pdf_to_images(pdf_file_path, output_dir):
    """Converts PDF to images and saves them to output_dir."""
    image_list = []
    counter = 0
    for i in pdf_to_image.pdf_to_images(pdf_file_path):
        name = os.path.join(output_dir, f"Document_{counter}.png")
        i.save(name)
        image_list.append(os.path.join(str(Path.cwd()), name))
        counter += 1
    return image_list

def detect_tables_in_images(image_list):
    """Detects tables in images and returns a TableMap."""
    TableMap = []
    for filepath in image_list:
        TableCoords = luminositybased.findTable(filepath, "borderless", "borderless")
        FormattedCoords = [luminositybased.convert_to_pairs(CordList) for CordList in TableCoords]
        TableMap.append(FormattedCoords)
    return TableMap

def cellularize_images(image_list, TableMap, page_num=0):
    """Splits the images into cells based on detected table coordinates."""
    locationlists = []
    for index, Table in enumerate(TableMap):
        locationlists.append(cellularize_Page_colrow(image_list[index], Table[1], Table[0], page_num + index))
    return locationlists

def process_all_images(all_filenames, ocr, reader):
    """Processes all cell images and collects results."""
    results = []
    for filename in tqdm(all_filenames, desc="Processing images"):
        result = process_image(filename, ocr, reader)
        results.append(result)
    return results

def process_results(results):
    """Processes OCR results and returns aggregated data."""
    table_data = {}
    total = 0
    bad = 0
    easyocr_count = 0
    paddleocr_count = 0
    low_confidence_results = []

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
            # Collect low-confidence results to display at the end
            low_confidence_results.append(
                f"Review needed for {filename}: {best_text} (Confidence: {best_confidence}, Source: {source})"
            )

        if row_index not in table_data:
            table_data[row_index] = {}
        table_data[row_index][col_index] = best_text

    return table_data, total, bad, easyocr_count, paddleocr_count

def write_results_to_csv(table_data, output_csv):
    """Writes the table data to a CSV file."""
    max_columns = max(max(cols.keys()) for cols in table_data.values())
    with open(output_csv, mode='w', newline='') as file:
        writer = csv.writer(file)
        for row_index in sorted(table_data.keys()):
            row = [table_data[row_index].get(col_index, "") for col_index in range(max_columns + 1)]
            writer.writerow(row)
    print(f"Results saved to {output_csv}")

def display_statistics(total, bad, easyocr_count, paddleocr_count):
    """Displays statistics about the OCR results."""
    if total > 0:
        print(f"Percentage less than 80% confidence score is {bad / total * 100:.2f}% with {bad} possibly wrong")
    else:
        print("No valid OCR results to calculate confidence percentage.")

    print("OCR verification complete. Results saved to CSV.")
    print(f"Results using EasyOCR: {easyocr_count}")
    print(f"Results using PaddleOCR: {paddleocr_count}")

def cleanup(storedir):
    """Delete temporary files and directory."""
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

def initialize_paddleocr(use_gpu):
    """Initializes and returns a PaddleOCR engine."""
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
    return ocr

def initialize_easyocr(use_gpu):
    """Initializes and returns an EasyOCR reader."""
    reader = easyocr.Reader(['en'], gpu=use_gpu)
    return reader

def main():
    start_time = time.time()

    storedir = "temp"
    if not os.path.exists(storedir):
        os.makedirs(storedir)

    pdf_file = Path("..") / "Examples" / "2Page_AUSTRIA_1890_T2_g0bp.pdf"
    if not pdf_file.exists():
        raise FileNotFoundError(f"PDF file not found: {pdf_file.resolve()}")

    # Convert PDF to images
    image_list = convert_pdf_to_images(str(pdf_file), storedir)

    # Detect tables and cellularize
    TableMap = detect_tables_in_images(image_list)
    locationlists = cellularize_images(image_list, TableMap)

    output_csv = 'output.csv'

    # Flatten the list of image filenames
    all_filenames = [filename for collection in locationlists for filename in collection]

    # Initialize OCR engines once in the main thread
    use_gpu = paddle.device.is_compiled_with_cuda()
    ocr = initialize_paddleocr(use_gpu)
    reader = initialize_easyocr(use_gpu)

    # Process images
    results = process_all_images(all_filenames, ocr, reader)

    # Process the results
    table_data, total, bad, easyocr_count, paddleocr_count = process_results(results)

    # Write results to CSV
    write_results_to_csv(table_data, output_csv)

    # Display statistics
    display_statistics(total, bad, easyocr_count, paddleocr_count)

    # Cleanup
    cleanup(storedir)

    end_time = time.time()
    elapsed_time = end_time - start_time
    print(f"Total execution time: {elapsed_time:.2f} seconds")

if __name__ == '__main__':
    main()
