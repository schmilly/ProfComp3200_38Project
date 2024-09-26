from PIL import Image
import random
import string
import os

OutputLocation = "temp"

def cellularize_Page_colrow(ImageLocation: str, colAr: list, rowAr: list, page_num):
    """
    Splits an image into cells based on provided column and row boundaries.

    This function takes an image from a specified location and divides it into smaller
    cells according to the specified pixel boundaries in `colAr` and `rowAr`.
    The cells are saved as PNG files in the designated output folder.

    @param ImageLocation: A string representing the path to the input image.
    @param colAr: A list of pairs representing the column boundaries in pixel coordinates.
                  Each pair defines the start and end of a column (e.g., [[colStart1, colEnd1], [colStart2, colEnd2], ...]).
    @param rowAr: A list of pairs representing the row boundaries in pixel coordinates.
                  Each pair defines the start and end of a row (e.g., [[rowStart1, rowEnd1], [rowStart2, rowEnd2], ...]).

    @return A list of strings, each representing the file path to a saved cell image.

    Example:
    --------
    cellularize_Page_colrow("image.png", [[0, 100], [100, 200]], [[0, 100], [100, 200]])

    Notes:
    - The top-left pixel of the input image is considered as [0, 0].
    - Each unit in the boundary arrays corresponds to a pixel in the image.
    - Cells are saved in the `OutputLocation` directory as PNG files.

    Exceptions:
    -----------
    - If the output directory already exists, a message is printed to the console.
    """

def cellularize_Page_colrow(ImageLocation: str, colAr: list, rowAr: list, page_num):
    """ 
    Splits an image into cells based on provided column and row boundaries, including page number. 
    The `colAr` and `rowAr` must be lists of tuples where each tuple represents valid (x1, y1, x2, y2) coordinates.
    """
    page = Image.open(ImageLocation)
    page_width, page_height = page.size
    OutputLocation = "output_directory"  # Specify your output directory here
    
    # Create output directory if it doesn't exist
    os.makedirs(OutputLocation, exist_ok=True)
    
    locationlist = []

    colcount = 0
    rowcount = 0

    # Process columns and rows, checking for boundary issues
    for col in colAr:
        rowcount = 0
        for row in rowAr:
            try:
                # Ensure the crop coordinates are within the image boundaries
                x1, y1 = max(col[0], 0), max(row[0], 0)  # Top-left corner, clipped to image bounds
                x2, y2 = min(col[2], page_width), min(row[3], page_height)  # Bottom-right corner, clipped to image bounds
                
                if x1 < x2 and y1 < y2:  # Ensure the box has a valid area
                    cell = page.crop((x1, y1, x2, y2))
                    filename = f"page_{page_num}_{colcount}_{rowcount}.png"
                    fullPath = os.path.join(OutputLocation, filename)
                    cell.save(fullPath)
                    locationlist.append(fullPath)
                else:
                    print(f"Skipping invalid crop region for col {colcount}, row {rowcount} on page {page_num}")
            except Exception as e:
                print(f"Error cropping cell at col {colcount}, row {rowcount} on page {page_num}: {e}")
            rowcount += 1
        colcount += 1

    return locationlist

def get_random_string(length):
    letters = string.ascii_lowercase
    result_str = ''.join(random.choice(letters) for i in range(length))
    return result_str
