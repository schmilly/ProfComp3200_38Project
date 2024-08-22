from pathlib import Path
from shash_code import *
from TableDetectionTests import *
from Cellularize import *
import os
import time


storedir="temp"
if not os.path.exists(storedir):
    os.makedirs(storedir)

image_list = []
counter = 0
for i in pdf_to_image.pdf_to_images("/home/schmilly/ProfComp3200_38Project/Examples/2Page_AUSTRIA_1890_T2_g0bp.pdf"):
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

