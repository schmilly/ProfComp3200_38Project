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
from pdf_to_image import *
from Cellularize import *
from OCRCompare import *
from paddleocr import PaddleOCR
from PIL import Image
import easyocr
import paddle
from pdf2image import convert_from_path
import luminosity_table_detection as ltd
from luminosity_table_detection import split_image_with_lines


def get_absolute_path_with_prefix(path):
    """Return the absolute path with the '\\?\' prefix if running on Windows to handle long paths."""
    if os.name == 'nt':
        return '\\\\?\\' + str(Path(path).resolve())
    return str(Path(path).resolve())

def setup_environment(storedir):
    """ Set up directories and environment variables for processing. """
    storedir = get_absolute_path_with_prefix(storedir)
    if not os.path.exists(storedir):
        os.makedirs(storedir)

def convert_pdf_to_images(pdf_file, storedir):
    """ Convert a PDF into images and store them in the specified directory. """
    pdf_file = Path(pdf_file)
    
    # Check if PDF file exists
    if not pdf_file.exists():
        raise FileNotFoundError(f"PDF file not found: {pdf_file.resolve()}")

    # Ensure the output directory exists
    storedir = Path(storedir)
    if not storedir.exists():
        storedir.mkdir(parents=True, exist_ok=True)

    image_list = []
    
    # Convert PDF to images using pdf2image
    for i, image in enumerate(convert_from_path(str(pdf_file))):
        image_name = storedir / f"Document_{i}.png"
        image.save(image_name)
        image_list.append(str(image_name))
    
    return image_list

def extract_tables_from_images(image_paths, custom_lines=None, table_detection_method='Peaks and Troughs'):
    """
    Extracts table coordinates using either provided custom lines or table detection methods.
    """
    table_map = {}
    for idx, image_path in enumerate(image_paths):
        print(f"Processing image {image_path}...")  # Log image being processed
        
        if custom_lines:
            # Use pre-provided custom lines (still extract the coordinates, not paths)
            lines = custom_lines
            table_map[idx] = lines  # Store the lines (coordinates) instead of image paths
        else:
            # Detect table coordinates (not image paths)
            try:
                if table_detection_method == 'Peaks and Troughs':
                    horizontal_positions, vertical_positions, _ = ltd.find_table_peaks_troughs(image_path)
                elif table_detection_method == 'Transitions':
                    horizontal_positions, vertical_positions, _ = ltd.find_table_transitions(image_path)
                else:
                    horizontal_positions, vertical_positions = [], []

                if not horizontal_positions and not vertical_positions:
                    raise ValueError("No table positions found")

                lines = []
                image = Image.open(image_path)
                width, height = image.size

                # Clip horizontal and vertical positions to avoid out-of-bounds errors
                horizontal_positions = [y for y in horizontal_positions if 0 <= y <= height]
                vertical_positions = [x for x in vertical_positions if 0 <= x <= width]

                # Convert horizontal positions to line coordinates
                for y in horizontal_positions:
                    line = (0, y, width, y)  # Horizontal lines from (0, y) to (width, y)
                    lines.append(line)
                
                # Convert vertical positions to line coordinates
                for x in vertical_positions:
                    line = (x, 0, x, height)  # Vertical lines from (x, 0) to (x, height)
                    lines.append(line)

                if not lines:
                    print(f"No lines detected for image {image_path}, using image edges.")
                    lines = [(0, 0, width, 0), (0, height, width, height), (0, 0, 0, height), (width, 0, width, height)]

                # Store the coordinates (lines) in the table map, not the image paths
                table_map[idx] = lines

            except Exception as e:
                print(f"Table extraction failed for image {image_path}: {e}")
                table_map[idx] = []  # Return an empty list if detection fails

    return table_map

def cellularize_tables(image_list, table_map, page_num):
    """ Cellularize pages based on detected table coordinates, creating bounding boxes for each cell. """
    location_lists = []

    for index, (image_path, table_coords) in enumerate(zip(image_list, table_map.values())):
        print(f"Processing image {image_path} with table_coords: {table_coords}")
        
        if not isinstance(table_coords, list) or not table_coords:
            print(f"No valid table coordinates found for image {image_path}. Skipping cellularization.")
            continue  # Skip processing if no valid table coordinates

        # Use split_image_with_lines to cellularize the image based on table coordinates
        cells = split_image_with_lines(image_path, table_coords)
        location_lists.append(cells)
    
    return location_lists

def initialize_paddleocr():
    """ Initialize PaddleOCR and automatically switch between GPU or CPU based on availability. """
    try:
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
        use_gpu=use_gpu
    )

def initialize_easyocr():
    """ Initialize EasyOCR with automatic GPU detection. """
    try:
        reader = easyocr.Reader(['en'], gpu=True)
        print("EasyOCR initialized using GPU")
    except Exception as e:
        print(f"Error initializing EasyOCR with GPU: {e}. Defaulting to CPU.")
        reader = easyocr.Reader(['en'], gpu=False)

    return reader

def configure_logging():
    """ Set all existing loggers to WARNING. """
    for logger_name in logging.root.manager.loggerDict:
        logging.getLogger(logger_name).setLevel(logging.WARNING)

def perform_ocr_on_images(location_lists, ocr, reader):
    """
    Perform OCR on images using both PaddleOCR and EasyOCR without batch processing.
    """
    table_data = {}
    total, bad, easyocr_count, paddleocr_count = 0, 0, 0, 0

    for collection in location_lists:
        for filename in collection:
            try:
                # Open the image and convert to RGB
                image = Image.open(filename).convert("RGB")

                # Perform OCR with PaddleOCR
                original_text, original_confidence = perform_paddle_ocr(image, return_confidence=True)
                processed_text, processed_confidence = perform_paddle_ocr(image, return_confidence=True)

                # Use EasyOCR only if PaddleOCR confidence is low
                if original_confidence < 0.8 and processed_confidence < 0.8:
                    easy_original_text, easy_original_conf = perform_easyocr(image)
                    easy_processed_text, easy_processed_conf = perform_easyocr(image)
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

                # Select the best result based on confidence
                best_text, best_confidence, source = max(results, key=lambda x: x[1])

                if best_confidence == 0:
                    print(f"Skipping invalid {filename}")
                    continue

                # Extract row and column index from filename
                parts = filename.rsplit('_', maxsplit=3)
                row_index = int(parts[-2])
                col_index = int(parts[-1].split('.')[0])

                if row_index not in table_data:
                    table_data[row_index] = {}

                table_data[row_index][col_index] = best_text

                # Count results
                if 'EasyOCR' in source:
                    easyocr_count += 1
                else:
                    paddleocr_count += 1

                total += 1
                if best_confidence < 0.8:
                    bad += 1
                    print(f"Review needed for {filename}: {best_text} (Confidence: {best_confidence}, Source: {source})")

            except Exception as e:
                print(f"Error processing {filename}: {e}")
                continue

    return table_data, total, bad, easyocr_count, paddleocr_count

def write_to_csv(all_table_data, output_csv):
    """ Write OCR results to a CSV file. """
    with open(output_csv, mode='w', newline='') as file:
        writer = csv.writer(file)
        for page, rows in sorted(all_table_data.items()):
            writer.writerow([f"Page {page}"])  
            max_columns = max((max(cols.keys()) for cols in rows.values()), default=-1) + 1
            for row_index in sorted(rows.keys()):
                row = [rows[row_index].get(col_index, "") for col_index in range(max_columns)]
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

def run_ocr_pipeline(pdf_file, storedir, output_csv):
    """
    Runs the entire OCR pipeline including:
    1. PDF conversion to images
    2. Table detection and cellularization (only on full-page images)
    3. OCR using both PaddleOCR and EasyOCR
    4. Saving results to CSV

    :param pdf_file: Path to the PDF file to be processed.
    :param storedir: Temporary directory to store images.
    :param output_csv: Path to the output CSV file.
    """
    start_time = time.time()
    
    # Set up environment and logging
    setup_environment(storedir)
    configure_logging()

    # Initialize OCR engines
    ocr = initialize_paddleocr()
    reader = initialize_easyocr()

    # Convert PDF to images
    image_list = convert_pdf_to_images(pdf_file, storedir)

    # Initialize tracking variables
    page_num = 0
    total, bad, easyocr_count, paddleocr_count = 0, 0, 0, 0
    all_table_data = {}

    # Process each image (page)
    for image_path in image_list:
        # Skip images that are already cells (avoid double processing)
        if '_cell_' in image_path:
            print(f"Skipping cellularization for already cropped cell: {image_path}")
            continue

        # Extract tables and cellularize the full-page image
        table_map = extract_tables_from_images([image_path])
        location_lists = cellularize_tables([image_path], table_map, page_num)

        # Perform OCR on the original cells, not on sub-cells
        table_data, t_total, t_bad, t_easyocr_count, t_paddleocr_count = perform_ocr_on_images(location_lists, ocr, reader)
        all_table_data[page_num] = table_data

        total += t_total
        bad += t_bad
        easyocr_count += t_easyocr_count
        paddleocr_count += t_paddleocr_count

        page_num += 1

    # Write the results to CSV
    write_to_csv(all_table_data, output_csv)

    # Log OCR quality statistics
    if total > 0:
        percentage_low_confidence = (bad / total) * 100
        print(f"Percentage of results with less than 80% confidence: {percentage_low_confidence:.2f}% ({bad} low confidence)")
    else:
        print("No OCR results to process.")
    
    print(f"Results saved to CSV. EasyOCR: {easyocr_count}, PaddleOCR: {paddleocr_count}")

    # Clean up temporary files
    cleanup(storedir)

    # Log total execution time
    end_time = time.time()
    print(f"Total execution time: {end_time - start_time:.2f} seconds")

    # Return summary for further use (like in the GUI)
    return all_table_data, total, bad, easyocr_count, paddleocr_count, end_time - start_time

def main():
    pdf_file = Path("..") / "Examples" / "2Page_AUSTRIA_1890_T2_g0bp.pdf"
    storedir = "temp"
    output_csv = 'output.csv'

    run_ocr_pipeline(pdf_file, storedir, output_csv)

if __name__ == "__main__":
    main()
