import os
os.environ['KMP_DUPLICATE_LIB_OK'] = 'True'
from pathlib import Path
from shash_code import *
from TableDetectionTests import *
from Cellularize import *
from OCRCompare import *
import time


start_time = time.time()

storedir="temp"
if not os.path.exists(storedir):
    os.makedirs(storedir)

pdf_file = Path("..") / "Examples" / "2Page_AUSTRIA_1890_T2_g0bp.pdf"
if not pdf_file.exists():
    raise FileNotFoundError(f"PDF file not found: {pdf_file.resolve()}")


image_list = []
counter = 0

for i in pdf_to_image.pdf_to_images(str(pdf_file)):
    name = os.path.join(storedir,"Document_" + str(counter) + ".png")
    i.save(name)
    image_list.append(os.path.join(str(Path.cwd()),name))
    counter=counter+1

TableMap = []
for filepath in image_list:
    TableCoords = luminositybased.findTable(filepath,"borderless","borderless")
    FormattedCoords = []
    for CordList in TableCoords:
        FormattedCoords.append(luminositybased.convert_to_pairs(CordList))
    TableMap.append(FormattedCoords)

locationlists = []
for index,Table in enumerate(TableMap):
    locationlists.append(cellularize_Page_colrow(image_list[index],Table[1],Table[0]))

#image_directory = 'Austria' #set this to be the directory containing all data cells
#Commented out and using locationlist input instead
output_csv = 'output.csv' 
table_data = {}    

ocr = PaddleOCR(use_angle_cls=True, lang='en',rec_model_dir='en_PP-OCRv4_rec',
    version='PP-OCRv4',
    det_db_thresh=0.35,
    det_db_box_thresh=0.45,
    det_db_unclip_ratio=1.8,
    cls_thresh=0.95,
    use_space_char=True,
    rec_image_shape='3, 48, 320',
    det_limit_side_len=960)
import logging

# Set all existing loggers to WARNING
for logger_name in logging.root.manager.loggerDict:
    logging.getLogger(logger_name).setLevel(logging.WARNING)

reader = easyocr.Reader(['en'], gpu=False)  # Set 'gpu=True' if GPU is available

total = 0
bad = 0
easyocr_count = 0
paddleocr_count = 0
#print(locationlists)
for collection in locationlists:
    for filename in collection:
        #if filename.endswith(".png"):
        parts = filename.split('_')
        row_index = int(parts[2])
        col_index = int(parts[3].split('.')[0])
    
        #image_path = os.path.join(storedir, filename)
        image_path = filename
        image = Image.open(image_path).convert("RGB")
        processed_image = preprocess_image(image)
        # OCR with PaddleOCR
        original_text, original_confidence = perform_paddle_ocr(image, return_confidence=True)
        processed_text, processed_confidence = perform_paddle_ocr(processed_image, return_confidence=True)
    
        # OCR with EasyOCR
        easy_original_text, easy_original_conf = perform_easyocr(image)
        easy_processed_text, easy_processed_conf = perform_easyocr(processed_image)
    
        # Determine the highest confidence result
        best_result = max(
            (original_text, original_confidence, 'Original Image, PaddleOCR'),
            (processed_text, processed_confidence, 'Processed Image, PaddleOCR'),
            (easy_original_text, easy_original_conf, 'Original Image, EasyOCR'),
            (easy_processed_text, easy_processed_conf, 'Processed Image, EasyOCR'),
            key=lambda x: x[1]  # Compare by confidence
        )
    
        if col_index == 0 and best_result[1] == 0:
            continue
        if 'EasyOCR' in best_result[2]:
            easyocr_count += 1
        else:
            paddleocr_count += 1
          
        total += 1
        
        if best_result[1] < 0.80:
            bad += 1
            print(f"Review needed for {filename}: {best_result[0]} (Confidence: {best_result[1]}, Source: {best_result[2]})")
            # To verify text via GUI manually for low confidence values
            #final_text = verify_ocr_results(filename, final_image, final_text) 
            #print(f"OCR Result for {filename}: {corrected_text}")  # Debug output
    
        if row_index not in table_data:
            table_data[row_index] = {}
        table_data[row_index][col_index] = best_result[0]

# Write the table data to a CSV file
max_columns = max(max(cols.keys()) for cols in table_data.values())
with open(output_csv, mode='w', newline='') as file:
    writer = csv.writer(file)
    for row_index in sorted(table_data.keys()):
        row = []
        for col_index in range(max_columns + 1):
            cell_text = table_data[row_index].get(col_index, "")
            row.append(cell_text)
        writer.writerow(row)
print(f"percentage less than 80 confidence score is {bad/total*100}% with {bad} possibly wrong")
print("OCR verification complete. Results saved to CSV.")
print(f"Results using EasyOCR: {easyocr_count}")
print(f"Results using PaddleOCR: {paddleocr_count}")

#Cleanup = comment to keep files
for collection in locationlists:
    for file in collection:
        os.remove(file)
os.rmdir(storedir)

end_time = time.time()
elapsed_time = end_time - start_time
print(f"Total execution time: {elapsed_time:.2f} seconds")
