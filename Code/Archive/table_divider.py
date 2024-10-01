"""
@file TableDividerApp.py
@brief A Tkinter-based application for manually selecting and dividing tables from PDF images.

@details
This script allows users to load images (converted from a PDF) and manually select regions (cells) 
by drawing rectangles on the image. The coordinates of the rectangles are stored, and the corresponding 
regions of the image can later be extracted as individual cells.

The application features:
- Left-click to select the top-left and bottom-right corners of a rectangle.
- Right-click to reset the current rectangle selection.
- The extracted cells can be accessed via the `extract_cells` method.

@class TableDividerApp
@brief Main application class for managing the image display and user interaction.

@details
This class handles image display, user interaction for selecting table cells, and storing the coordinates of the selected regions. 
It includes methods for drawing rectangles on the image, handling mouse events, and extracting the selected regions (cells) from the image.

@functions:
- __init__(self, root, images): Initializes the application with a Tkinter root window and a list of images.
- setup_ui(self): Sets up the user interface, including a canvas for displaying images and event bindings for mouse interactions.
- show_image(self, image): Displays the specified image on the canvas.
- on_click(self, event): Handles left-click events to select the top-left and bottom-right corners of a rectangle.
- on_right_click(self, event): Handles right-click events to reset the current rectangle selection.
- draw_rectangle(self): Draws a rectangle on the canvas based on the selected coordinates.
- extract_cells(self): Extracts and returns the image regions (cells) based on the stored rectangle coordinates.

@params:
- root: The Tkinter root window.
- images: A list of PIL Image objects representing the pages of a PDF, converted to images.

@usage:
- Run the application by creating a Tkinter root window and passing a list of images (converted from a PDF) to the `TableDividerApp` class.
- Left-click on the image to select table cell boundaries. Once selected, the coordinates will be stored, and the corresponding regions can be extracted using `extract_cells`.
"""


import tkinter as tk
from PIL import Image, ImageTk
from pdf_to_images import pdf_to_images

class TableDividerApp:
    def __init__(self, root, images):
        self.root = root
        self.images = images
        self.current_image = 0
        self.rect_coords = []
        self.cell_coords = []
        self.setup_ui()

    def setup_ui(self):
        self.canvas = tk.Canvas(self.root, width=800, height=600)
        self.canvas.pack()
        
        self.show_image(self.images[self.current_image])

        self.canvas.bind("<Button-1>", self.on_click)
        self.canvas.bind("<Button-3>", self.on_right_click)

    def show_image(self, image):
        self.tk_image = ImageTk.PhotoImage(image)
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.tk_image)

    def on_click(self, event):
        x, y = event.x, event.y
        self.rect_coords.append((x, y))
        if len(self.rect_coords) == 2:
            self.draw_rectangle()
            self.cell_coords.append(self.rect_coords)
            self.rect_coords = []

    def on_right_click(self, event):
        self.rect_coords = []
        self.canvas.delete("rect")

    def draw_rectangle(self):
        x1, y1 = self.rect_coords[0]
        x2, y2 = self.rect_coords[1]
        self.canvas.create_rectangle(x1, y1, x2, y2, outline='red', tag="rect")
        print(f"Rectangle from ({x1}, {y1}) to ({x2}, {y2})")
        
    def extract_cells(self):
        image = self.images[self.current_image]
        cells = []
        for coords in self.cell_coords:
            x1, y1 = coords[0]
            x2, y2 = coords[1]
            cell = image.crop((x1, y1, x2, y2))
            cells.append(cell)
        return cells

if __name__ == "__main__":
    root = tk.Tk()
    images = pdf_to_images('sample.pdf')
    app = TableDividerApp(root, images)
    root.mainloop()
