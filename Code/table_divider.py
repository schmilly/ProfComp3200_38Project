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
