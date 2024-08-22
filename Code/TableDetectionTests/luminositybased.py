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





def findTable(image_path="Image/Path/here",HorizontalState = "border",VerticalState = "border",horizontalgap = 15/2077, verticalgap = 80/1474):

    #Gap between peaks/troughs before consider new peak/trough

    image = Image.open(image_path)
    # Process image
    wid, hgt = image.size

    luminosity = calculate_luminosity(image)
    if (HorizontalState == "border"):
        Horizontal = find_peaks(1,luminosity,round(hgt*horizontalgap))
    else:
        Horizontal = find_troughs(1,luminosity,round(hgt*horizontalgap)) 
    if (VerticalState == "border"):
        Vertical = find_peaks(0,luminosity,round(wid*verticalgap))
    else:
        Vertical = find_troughs(0,luminosity,round(wid*verticalgap)) 
    

    result_image = draw_lines(image, Horizontal) 
    final_image = draw_vertical_lines(image, Vertical)

    #final_image.save('output_image_with_lines.png')
    final_image.show()

    return [Horizontal,Vertical]

def convert_to_pairs(lst):
    # Create a list of lists where each sublist contains two consecutive elements
    return [[lst[i], lst[i + 1]] for i in range(len(lst) - 1)]
