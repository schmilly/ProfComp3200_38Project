from PIL import Image
import random
import string
import os

OutputLocation = "temp"

# Turns image into cells based on inputs; 
# Cell edges have perpendicular to image dimensions
# 
# Arguments:
#   ImageLocation: A string to the location of the image
#   colArr: A list of columns bound co-ordinates in pair formats 
#       i.e: [row1[rowStart,rowEnd],row2[rowStart,rowEnd]..e.t.c.]
#   rowArr: a list of row bound co-ordinates in pair formats; Same as colArr
#   Notes: Co-ordinates for colArr and rowArr:
#       - Based on pixels - top left pixel of the input image being equal to [0,0] and 1 unit = 1 pixel
def cellularize_Page_colrow(ImageLocation: str,colAr: list,rowAr: list):
    #Verification TBD
    page = Image.open(r""+ImageLocation)
    try:
        os.mkdir(OutputLocation)
    except:
        print(OutputLocation + " folder already exists!")
    
    pageID = get_random_string(7) 
    count = 0
    colcount = 0
    rowcount = 0
    locationlist = []
    #Verify colArr and rowArr TBD 
    for col in colAr:
        colcount = 0
        for row in rowAr:
            cell = page.crop((col[0],row[0],col[1],row[1]))
            filename = ("page_"+ pageID +"_"+ str(colcount) +"_"+ str(rowcount)+ ".png")
            fullPath = os.path.join(OutputLocation,filename)
            file = open(fullPath,"xb")
            cell.save(file,None)
            locationlist.append(fullPath)
            colcount = colcount + 1
        rowcount = rowcount + 1
    return locationlist
    

def get_random_string(length):
    # choose from all lowercase letter
    letters = string.ascii_lowercase
    result_str = ''.join(random.choice(letters) for i in range(length))
    return result_str
