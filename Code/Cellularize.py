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
    """ Splits an image into cells based on provided column and row boundaries, including page number. """
    page = Image.open(ImageLocation)
    try:
        os.mkdir(OutputLocation)
    except:
        print(f"{OutputLocation} folder already exists!")
    
    pageID = get_random_string(7) 
    count = 0
    colcount = 0
    rowcount = 0
    locationlist = []
    # Process columns and rows, and name files including the page number
    for col in colAr:
        colcount = 0
        for row in rowAr:
            cell = page.crop((col[0], row[0], col[1], row[1]))
            filename = f"page_{page_num}_{colcount}_{rowcount}.png"
            fullPath = os.path.join(OutputLocation, filename)
            cell.save(fullPath)
            locationlist.append(fullPath)
            colcount += 1
        rowcount += 1
    return locationlist

    

def get_random_string(length):
    letters = string.ascii_lowercase
    result_str = ''.join(random.choice(letters) for i in range(length))
    return result_str
