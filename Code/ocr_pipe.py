import os
import time
import logging
import csv
import concurrent.futures
from pathlib import Path
from pdf_to_image import *
# from TableDetection import *
from Cellularize import *
from OCRCompare import *
from paddleocr import PaddleOCR
from PIL import Image
import easyocr
import paddle
from pdf2image import convert_from_path
import luminosity_table_detection as ltd
from luminosity_table_detection import split_image_with_lines
import tkinter as tk
from PIL import ImageTk

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

def extract_tables_from_images(image_paths, table_detection_method='Peaks and Troughs'):
    """
    Extracts table coordinates using table detection methods.
    """
    table_map = {}
    for idx, image_path in enumerate(image_paths):
        print(f"Processing image {image_path}...")  # Log image being processed
        
        # Detect table coordinates
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

def perform_paddle_ocr(image, return_confidence=False):
    """ Perform OCR using PaddleOCR on a single image."""
    result = ocr.ocr(image, cls=True)
    text = ""
    confidence = 0.0
    for line in result:
        for word_info in line:
            word, score = word_info[1]
            text += word + " "
            if score > confidence:
                confidence = score
    return text.strip(), confidence if return_confidence else text.strip()

def perform_easyocr(image):
    """ Perform OCR using EasyOCR on a single image."""
    result = reader.readtext(np.array(image))
    text = ""
    confidence = 0.0
    for bbox, word, score in result:
        text += word + " "
        if score > confidence:
            confidence = score
    return text.strip(), confidence

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
    with open(output_csv, mode='w', newline='', encoding='utf-8') as file:
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

def run_ocr_pipeline(pdf_file, storedir, output_csv, ocr_progress, ocr_cancel_event):
    """
    Runs the entire OCR pipeline including:
    1. PDF conversion to images
    2. Table detection and cellularization (only on full-page images)
    3. OCR using both PaddleOCR and EasyOCR
    4. Saving results to CSV

    :param pdf_file: Path to the PDF file to be processed.
    :param storedir: Temporary directory to store images.
    :param output_csv: Path to the output CSV file.
    :param ocr_progress: pyqtSignal(int, int) to emit progress updates.
    :param ocr_cancel_event: threading.Event to signal cancellation of OCR process.
    :return: Tuple containing all_table_data, total, bad, easyocr_count, paddleocr_count, processing_time
    """
    start_time = time.time()
    
    try:
        # Step 1: Set up environment and logging
        setup_environment(storedir)
        configure_logging()
        ocr_progress.emit(5, 100)  # 5% complete
        
        # Step 2: Initialize OCR engines
        ocr = initialize_paddleocr()
        reader = initialize_easyocr()
        ocr_progress.emit(10, 100)  # 10% complete
        
        # Step 3: Convert PDF to images
        image_list = convert_pdf_to_images(pdf_file, storedir)
        if ocr_cancel_event.is_set():
            raise Exception("OCR process was cancelled during PDF conversion.")
        ocr_progress.emit(20, 100)  # 20% complete
        
        # Step 4: Initialize tracking variables
        page_num = 0
        total, bad, easyocr_count, paddleocr_count = 0, 0, 0, 0
        all_table_data = {}
        
        total_pages = len(image_list)
        for idx, image_path in enumerate(image_list):
            if ocr_cancel_event.is_set():
                raise Exception("OCR process was cancelled during processing images.")
            
            # Emit progress
            current_progress = 20 + int((idx / total_pages) * 60)  # 20% to 80%
            ocr_progress.emit(current_progress, 100)
            
            # Skip images that are already cells (avoid double processing)
            if '_cell_' in image_path:
                logging.info(f"Skipping cellularization for already cropped cell: {image_path}")
                continue

            # Extract tables and cellularize the full-page image
            table_map = extract_tables_from_images([image_path], table_detection_method='Peaks and Troughs')  # Specify method as needed
            location_lists = cellularize_tables([image_path], table_map, page_num)
            
            if ocr_cancel_event.is_set():
                raise Exception("OCR process was cancelled during table extraction and cellularization.")
            
            # Perform OCR on the original cells, not on sub-cells
            table_data, t_total, t_bad, t_easyocr_count, t_paddleocr_count = perform_ocr_on_images(location_lists, ocr, reader)
            all_table_data[page_num] = table_data

            # Update tracking variables
            total += t_total
            bad += t_bad
            easyocr_count += t_easyocr_count
            paddleocr_count += t_paddleocr_count

            page_num += 1

        if ocr_cancel_event.is_set():
            raise Exception("OCR process was cancelled after processing all images.")

        # Step 5: Write the results to CSV
        write_to_csv(all_table_data, output_csv)
        ocr_progress.emit(90, 100)  # 90% complete

        # Step 6: Log OCR quality statistics
        if total > 0:
            percentage_low_confidence = (bad / total) * 100
            logging.info(f"Percentage of results with less than 80% confidence: {percentage_low_confidence:.2f}% ({bad} low confidence)")
            ocr_progress.emit(95, 100)  # 95% complete
        else:
            logging.info("No OCR results to process.")
            ocr_progress.emit(95, 100)  # 95% complete
        
        logging.info(f"Results saved to CSV. EasyOCR: {easyocr_count}, PaddleOCR: {paddleocr_count}")
        ocr_progress.emit(98, 100)  # 98% complete

        # Step 7: Calculate and log total execution time
        end_time = time.time()
        processing_time = end_time - start_time
        logging.info(f"Total execution time: {processing_time:.2f} seconds")
        ocr_progress.emit(100, 100)  # 100% complete

        # Return summary for further use (like in the GUI)
        return all_table_data, total, bad, easyocr_count, paddleocr_count, processing_time

    except Exception as e:
        logging.error(f"An error occurred during OCR pipeline: {e}", exc_info=True)
        raise  # Reraise the exception to be caught by the worker's try-except

    finally:
        # Step 8: Cleanup temporary images regardless of success or failure
        cleanup(storedir)
        logging.info("Cleaned up temporary images.")
        # Optionally, emit final progress if not already at 100%
        if not ocr_cancel_event.is_set():
            ocr_progress.emit(100, 100)

def start_manual_table_detection(images):
    """Launch manual table detection if OCR fails."""
    root = tk.Tk()
    manual_table_app = TableDividerApp(root, images)  # Pass the images to the manual tool
    root.mainloop()

def run_ocr_pipeline(pdf_file, storedir, output_csv, ocr_progress, ocr_cancel_event):
    try:
        setup_environment(storedir)
        configure_logging()
        ocr = initialize_paddleocr()
        reader = initialize_easyocr()

        image_list = convert_pdf_to_images(pdf_file, storedir)
        total_pages = len(image_list)
        all_table_data = {}

        for idx, image_path in enumerate(image_list):
            if ocr_cancel_event.is_set():
                raise Exception("OCR process was cancelled during processing images.")

            table_map = extract_tables_from_images([image_path])
            if not table_map[idx]:
                print(f"OCR failed on {image_path}. Triggering manual table detection.")
                # Call manual table detection here when OCR fails or tables aren't detected
                pil_images = [Image.open(image_path) for image_path in image_list]
                start_manual_table_detection(pil_images)
                break  # Break or exit if you want to skip further OCR processing
            
            location_lists = cellularize_tables([image_path], table_map, idx)
            table_data, total, bad, easyocr_count, paddleocr_count = perform_ocr_on_images(location_lists, ocr, reader)
            all_table_data[idx] = table_data

        write_to_csv(all_table_data, output_csv)

    except Exception as e:
        logging.error(f"An error occurred during OCR pipeline: {e}", exc_info=True)
        raise
    finally:
        cleanup(storedir)