"""
@file RunThroughRefactor.py
@brief A script for processing PDFs into images, extracting tables, performing OCR using PaddleOCR and EasyOCR, and saving results to a CSV file.

@details
This script performs the following steps:
1. Converts a PDF document into a series of images.
2. Extracts table coordinates from the images.
3. Cellularizes the images into smaller regions based on table coordinates.
4. Performs OCR on both the original and preprocessed images using PaddleOCR and EasyOCR, with automatic GPU/CPU switching based on hardware availability.
5. Selects the OCR result with the highest confidence for each region.
6. Saves the OCR results into a CSV file.
7. Outputs a summary of the OCR results, including the percentage of low-confidence results.

@functions:
- setup_environment: Configures the environment and sets up necessary directories.
- convert_pdf_to_images: Converts a PDF document into images and saves them in the specified directory.
- extract_tables_from_images: Extracts table coordinates from the images.
- cellularize_tables: Splits images into smaller regions based on table coordinates.
- initialize_paddleocr: Initializes the PaddleOCR engine, automatically detecting and utilizing GPU if available, otherwise defaults to CPU.
- initialize_easyocr: Initializes the EasyOCR engine, automatically detecting and utilizing GPU if available, otherwise defaults to CPU.
- configure_logging: Configures logging to reduce verbosity of other libraries used in the script.
- perform_ocr_on_images: Performs OCR using both PaddleOCR and EasyOCR, applying batch processing and parallel execution, and returns the highest confidence result for each image region.
- write_to_csv: Saves the OCR results into a CSV file.
- cleanup: Cleans up temporary files and directories created during the process.
- main: Orchestrates the entire process from PDF conversion, OCR processing, and saving results to CSV, including cleanup.

@params:
- storedir: Directory used to store intermediate results (e.g., images).
- pdf_file: Path to the input PDF file to be processed.
- output_csv: Path to the output CSV file where OCR results are saved.
- batch_size: Number of images to process concurrently during OCR operations (default is 4).
"""


import os

os.environ['KMP_DUPLICATE_LIB_OK'] = 'True'

import time
import logging
import csv
import concurrent.futures

from pathlib import Path
from shash_code import *
from TableDetectionTests import *
from Cellularize import *
from OCRCompare import *
from paddleocr import PaddleOCR
from PIL import Image
import easyocr
import paddle


def setup_environment(storedir):
    """ Set up directories and environment variables for processing. """
    if not os.path.exists(storedir):
        os.makedirs(storedir)

def convert_pdf_to_images(pdf_file, storedir):
    """ Convert a PDF into images and store them in the specified directory. """
    if not pdf_file.exists():
        raise FileNotFoundError(f"PDF file not found: {pdf_file.resolve()}")

    image_list = []
    counter = 0
    for i in pdf_to_image.pdf_to_images(str(pdf_file)):
        name = os.path.join(storedir, f"Document_{counter}.png")
        i.save(name)
        image_list.append(os.path.join(str(Path.cwd()), name))
        counter += 1
    return image_list

def extract_tables_from_images(image_list):
    """ Extract tables from images and return a list of table coordinates. """
    table_map = []
    for filepath in image_list:
        table_coords = luminositybased.findTable(filepath, "borderless", "borderless")
        formatted_coords = [luminositybased.convert_to_pairs(cord_list) for cord_list in table_coords]
        table_map.append(formatted_coords)
    return table_map

def cellularize_tables(image_list, table_map):
    """ Cellularize pages based on detected table coordinates. """
    location_lists = []
    for index, table in enumerate(table_map):
        location_lists.append(cellularize_Page_colrow(image_list[index], table[1], table[0]))
    return location_lists

def initialize_paddleocr():
    """ Initialize PaddleOCR and automatically switch between GPU or CPU based on availability. """
    try:
        # Automatically detect if GPU is available
        use_gpu = paddle.device.is_compiled_with_cuda() and paddle.device.get_device().startswith('gpu')
        paddle.set_device('gpu' if use_gpu else 'cpu')  # Set GPU if available, otherwise CPU
        print(f"PaddleOCR initialized using {'GPU' if use_gpu else 'CPU'}")
    except Exception as e:
        print(f"Error initializing PaddleOCR: {e}. Defaulting to CPU.")
        use_gpu = False
        paddle.set_device('cpu')

    return PaddleOCR(
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
        use_gpu=use_gpu  # Enable GPU if available
    )

def initialize_easyocr():
    """ Initialize EasyOCR with automatic GPU detection. """
    try:
        # EasyOCR uses GPU if it detects one
        reader = easyocr.Reader(['en'], gpu=True)  # Try initializing with GPU
        print("EasyOCR initialized using GPU")
    except Exception as e:
        print(f"Error initializing EasyOCR with GPU: {e}. Defaulting to CPU.")
        reader = easyocr.Reader(['en'], gpu=False)  # Fallback to CPU

    return reader

def configure_logging():
    """ Set all existing loggers to WARNING. """
    for logger_name in logging.root.manager.loggerDict:
        logging.getLogger(logger_name).setLevel(logging.WARNING)

def perform_ocr_on_images(location_lists, ocr, reader, batch_size=4):
    """
    Perform OCR on images using both PaddleOCR and EasyOCR with optimizations: 
    batch processing, parallel execution, confidence thresholding, and GPU acceleration.
    """
    table_data = {}
    total, bad, easyocr_count, paddleocr_count = 0, 0, 0, 0

    def process_image_batch(batch):
        nonlocal total, bad, easyocr_count, paddleocr_count
        batch_results = []
        
        # Load images and preprocess them (no downsampling)
        images = [Image.open(filename).convert("RGB") for filename in batch]

        # Perform OCR with PaddleOCR
        original_texts, original_confidences = zip(*[perform_paddle_ocr(img, return_confidence=True) for img in images])
        processed_texts, processed_confidences = zip(*[perform_paddle_ocr(img, return_confidence=True) for img in images])

        for i, filename in enumerate(batch):
            # Parse the row and column indices
            parts = filename.rsplit('_', maxsplit=3)
            try:
                row_index = int(parts[-2])  # Row index
                col_index = int(parts[-1].split('.')[0])  # Column index (before .png)
            except (ValueError, IndexError) as e:
                print(f"Error processing filename {filename}: {e}")
                continue  # Skip this file if the filename format is incorrect

            original_text, original_confidence = original_texts[i], original_confidences[i]
            processed_text, processed_confidence = processed_texts[i], processed_confidences[i]

            # Use EasyOCR only if PaddleOCR confidence is low
            if original_confidence < 0.8 and processed_confidence < 0.8:
                easy_original_text, easy_original_conf = perform_easyocr(images[i])
                easy_processed_text, easy_processed_conf = perform_easyocr(images[i])
                results = [
                    (original_text, original_confidence, 'Original Image, PaddleOCR'),
                    (processed_text, processed_confidence, 'Processed Image, PaddleOCR'),
                    (easy_original_text, easy_original_conf, 'Original Image, EasyOCR'),
                    (easy_processed_text, easy_processed_conf, 'Processed Image, EasyOCR')
                ]
            else:
                results = [
                    (original_text, original_confidence, 'Original Image, PaddleOCR'),
                    (processed_text, processed_confidence, 'Processed Image, PaddleOCR')
                ]

            # Select the best result with the highest confidence
            best_text, best_confidence, source = max(results, key=lambda x: x[1])
            if best_confidence == 0:  # Skip blank cells
                continue

            if 'EasyOCR' in source:
                easyocr_count += 1
            else:
                paddleocr_count += 1

            total += 1
            if best_confidence < 0.8:
                bad += 1
                print(f"Review needed for {filename}: {best_text} (Confidence: {best_confidence}, Source: {source})")

            batch_results.append((row_index, col_index, best_text))

        return batch_results

    # Parallelize the processing with a ThreadPoolExecutor
    with concurrent.futures.ThreadPoolExecutor() as executor:
        for collection in location_lists:
            # Process images in batches
            batches = [collection[i:i + batch_size] for i in range(0, len(collection), batch_size)]
            futures = [executor.submit(process_image_batch, batch) for batch in batches]

            for future in concurrent.futures.as_completed(futures):
                batch_results = future.result()
                for row_index, col_index, best_text in batch_results:
                    if row_index not in table_data:
                        table_data[row_index] = {}
                    table_data[row_index][col_index] = best_text

    return table_data, total, bad, easyocr_count, paddleocr_count

def write_to_csv(table_data, output_csv):
    """ Write table data to a CSV file. """
    max_columns = max(max(cols.keys()) for cols in table_data.values())
    with open(output_csv, mode='w', newline='') as file:
        writer = csv.writer(file)
        for row_index in sorted(table_data.keys()):
            row = [table_data[row_index].get(col_index, "") for col_index in range(max_columns + 1)]
            writer.writerow(row)

def cleanup(storedir):
    """ Cleanup temporary files and directories. """
    for file in os.listdir(storedir):
        try:
            os.remove(os.path.join(storedir, file))
        except Exception as e:
            print(f"Error deleting file {file}: {e}")

    try:
        os.rmdir(storedir)
    except Exception as e:
        print(f"Error removing directory {storedir}: {e}")

def main():
    start_time = time.time()

    storedir = "temp"
    setup_environment(storedir)
    configure_logging()
    ocr = initialize_paddleocr()
    reader = easyocr.Reader(['en'], gpu=False)

    pdf_file = Path("..") / "Examples" / "2Page_AUSTRIA_1890_T2_g0bp.pdf"
    image_list = convert_pdf_to_images(pdf_file, storedir)

    table_map = extract_tables_from_images(image_list)
    location_lists = cellularize_tables(image_list, table_map)

    table_data, total, bad, easyocr_count, paddleocr_count = perform_ocr_on_images(location_lists, ocr, reader)

    write_to_csv(table_data, 'output.csv')

    print(f"Percentage of results with less than 80% confidence: {bad / total * 100:.2f}% ({bad} low confidence)")
    print(f"Results saved to CSV. EasyOCR: {easyocr_count}, PaddleOCR: {paddleocr_count}")

    cleanup(storedir)

    end_time = time.time()
    print(f"Total execution time: {end_time - start_time:.2f} seconds")

if __name__ == "__main__":
    main()
