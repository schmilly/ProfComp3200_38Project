# table_divider.py
import tkinter as tk
from PIL import Image, ImageTk

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
        
        next_button = tk.Button(self.root, text="Next Page", command=self.next_page)
        next_button.pack(side=tk.LEFT)
        
        prev_button = tk.Button(self.root, text="Previous Page", command=self.prev_page)
        prev_button.pack(side=tk.LEFT)
        
        save_button = tk.Button(self.root, text="Save Coordinates", command=self.save_coordinates)
        save_button.pack(side=tk.LEFT)

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

    def next_page(self):
        if self.current_image < len(self.images) - 1:
            self.current_image += 1
            self.show_image(self.images[self.current_image])

    def prev_page(self):
        if self.current_image > 0:
            self.current_image -= 1
            self.show_image(self.images[self.current_image])

    def save_coordinates(self):
        with open('cell_coordinates.txt', 'w') as file:
            for coords in self.cell_coords:
                file.write(f"{coords}\n")
        print("Coordinates saved.")
