from table_ocr import *

# Instantiation of the image
img = Image(src="/home/schmilly/ProfComp3200_38Project/Examples/PageExport.png")

# Table identification
img_tables = img.extract_cells()

# Result of table identification
print (img_tables)




