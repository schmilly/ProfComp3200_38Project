import tkinter as tk
from PIL import Image, ImageTk

class TableDividerApp:
    def __init__(self, root, images):
        self.root = root
        self.images = images
        self.current_image = 0
        self.rectangles = []
        self.start_x = None
        self.start_y = None
        self.setup_ui()

    def setup_ui(self):
        self.canvas = tk.Canvas(self.root, width=800, height=600)
        self.canvas.pack()
        
        self.show_image(self.images[self.current_image])

        self.canvas.bind("<Button-1>", self.on_click)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)

        self.save_button = tk.Button(self.root, text="Save Tables", command=self.save_tables)
        self.save_button.pack()

    def show_image(self, image):
        self.tk_image = ImageTk.PhotoImage(image)
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.tk_image)

    def on_click(self, event):
        self.start_x = event.x
        self.start_y = event.y
        self.rect = self.canvas.create_rectangle(self.start_x, self.start_y, self.start_x, self.start_y, outline='red')

    def on_drag(self, event):
        self.canvas.coords(self.rect, self.start_x, self.start_y, event.x, event.y)

    def on_release(self, event):
        end_x, end_y = event.x, event.y
        self.rectangles.append((self.start_x, self.start_y, end_x, end_y))
        print(f"Rectangle from ({self.start_x}, {self.start_y}) to ({end_x}, {end_y})")

    def save_tables(self):
        for idx, (start_x, start_y, end_x, end_y) in enumerate(self.rectangles):
            cropped_image = self.images[self.current_image].crop((start_x, start_y, end_x, end_y))
            cropped_image.save(f'table_{self.current_image}_{idx}.png')
        print("Tables saved.")
