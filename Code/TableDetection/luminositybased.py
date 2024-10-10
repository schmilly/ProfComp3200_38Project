from PIL import Image, ImageDraw
import numpy as np

def calculate_luminosity(image):
    # Convert the image to RGB (if it's not already)
    image = image.convert('RGB')
    pixels = np.array(image)
    # Apply luminosity formula
    luminosity = 0.299 * pixels[:, :, 0] + 0.587 * pixels[:, :, 1] + 0.114 * pixels[:, :, 2]
    return luminosity

def find_peaks(axis,luminosity,pointgap):
    # Calculate the average luminosity
    avg_luminosity = np.mean(luminosity, axis)
    # Find peaks: we consider a point as a peak if it's lower than its neighbors
    peaks = []
    error_count=0
    for i in range(1, len(avg_luminosity) - 1): 
       

        inRange = False

        for iasa in range(1, pointgap):
            try:
                if avg_luminosity[i] < avg_luminosity[i - iasa] and avg_luminosity[i] < avg_luminosity[i + iasa]:
                    inRange = True
                else:
                    inRange = False
                    break
            except:
                error_count = error_count + 1 
        if (inRange):
            peaks.append(i)

    return peaks


def find_troughs(axis,luminosity,pointgap):
    # Calculate the average luminosity for each column
    avg_luminosity = np.mean(luminosity, axis)
    # Find troughs: we consider a point as a trough if it's lower than its neighbors
    troughs = []
    error_count=0
    for i in range(1, len(avg_luminosity) - 1):
        #print(avg_luminosity[i])
        
        inRange = False

        #print(avg_luminosity[i])
        for iasa in range(1, pointgap):

            try:
                if avg_luminosity[i] > avg_luminosity[i - iasa] and avg_luminosity[i] > avg_luminosity[i + iasa]:
                    inRange = True
                else:
                    inRange = False
                    break
            except:
                error_count = error_count + 1 
        if (inRange):
            troughs.append(i)

    return troughs


def draw_lines(image, lines):
    draw = ImageDraw.Draw(image)
    width, height = image.size
    for x, line in enumerate(lines):
        if (line-lines[x-1] > 5):
            draw.line([(0, line), (width, line)], fill='red', width=1)
    return image

def draw_vertical_lines(image, lines):
    draw = ImageDraw.Draw(image)
    width, height = image.size
    for line in lines:
        draw.line([(line, 0), (line, height)], fill='blue', width=1)
    return image





from PIL import Image

def findTable(
    image_path,
    HorizontalState="border",
    VerticalState="border",
    horizontalgap_ratio=17/2077,
    verticalgap_ratio=80/1474,
    manual_horizontal_lines=None,
    manual_vertical_lines=None
):
    """
    Detects tables in an image by finding horizontal and vertical lines.
    Merges manual lines with automatically detected ones.

    :param image_path: Path to the image file.
    :param HorizontalState: Mode for horizontal line detection ("border" or other).
    :param VerticalState: Mode for vertical line detection ("border" or other).
    :param horizontalgap_ratio: Ratio to determine the gap for horizontal lines.
    :param verticalgap_ratio: Ratio to determine the gap for vertical lines.
    :param manual_horizontal_lines: List of manual horizontal line positions (y-coordinates).
    :param manual_vertical_lines: List of manual vertical line positions (x-coordinates).
    :return: List containing two lists: [horizontal_lines, vertical_lines].
    """
    # Open the image
    image = Image.open(image_path)
    wid, hgt = image.size

    # Calculate luminosity (assuming this function is defined)
    luminosity = calculate_luminosity(image)

    # Detect automatic horizontal lines
    if HorizontalState == "border":
        auto_horizontal = find_peaks(1, luminosity, round(hgt * horizontalgap_ratio))
        
    else:
        auto_horizontal = find_troughs(1, luminosity, round(hgt * horizontalgap_ratio))


    # Detect automatic vertical lines
    if VerticalState == "border":
        auto_vertical = find_peaks(1, luminosity, round(wid * verticalgap_ratio)
        )
    else:
        auto_vertical = find_troughs(1, luminosity, round(wid * verticalgap_ratio)
        )

    # Merge manual lines with automatic lines
    combined_horizontal = auto_horizontal.copy()
    combined_vertical = auto_vertical.copy()

    if manual_horizontal_lines:
        combined_horizontal.extend(manual_horizontal_lines)
    
    if manual_vertical_lines:
        combined_vertical.extend(manual_vertical_lines)
    
    # Remove duplicates and sort
    combined_horizontal = sorted(set(combined_horizontal))
    combined_vertical = sorted(set(combined_vertical))

    # Draw lines on the image (optional for visualization)
    result_image = draw_lines(image, combined_horizontal)
    final_image = draw_vertical_lines(result_image, combined_vertical)

    # Save or display the final image if needed
    # final_image.save('output_image_with_lines.png')
    # final_image.show()

    return [combined_horizontal, combined_vertical]


def convert_to_pairs(lst):
    # Create a list of lists where each sublist contains two consecutive elements
    return [[lst[i], lst[i + 1]] for i in range(len(lst) - 1)]
