import tkinter as tk
from tkinter import filedialog
from pdf2image import convert_from_path
from PIL import Image, ImageTk

class TableDividerApp:
    def __init__(self, root, images):
        self.root = root
        self.images = images
        self.current_image = 0
        self.rectangles = []
        self.setup_ui()

    def setup_ui(self):
        self.canvas = tk.Canvas(self.root, width=800, height=600, scrollregion=(0, 0, self.images[0].width, self.images[0].height))
        self.canvas.pack(expand=tk.YES, fill=tk.BOTH)
        
        hbar = tk.Scrollbar(self.root, orient=tk.HORIZONTAL)
        hbar.pack(side=tk.BOTTOM, fill=tk.X)
        hbar.config(command=self.canvas.xview)
        
        vbar = tk.Scrollbar(self.root, orient=tk.VERTICAL)
        vbar.pack(side=tk.RIGHT, fill=tk.Y)
        vbar.config(command=self.canvas.yview)
        
        self.canvas.config(xscrollcommand=hbar.set, yscrollcommand=vbar.set)
        
        self.show_image(self.images[self.current_image])

        self.canvas.bind("<Button-1>", self.on_left_click)
        self.canvas.bind("<Button-3>", self.on_right_click)
        self.canvas.bind("<B3-Motion>", self.on_drag)

        self.save_button = tk.Button(self.root, text="Next Page", command=self.next_page)
        self.save_button.pack(side=tk.LEFT)
        
        self.prev_button = tk.Button(self.root, text="Previous Page", command=self.prev_page)
        self.prev_button.pack(side=tk.RIGHT)
        
        self.zoom_in_button = tk.Button(self.root, text="Zoom In", command=lambda: self.zoom(1.2))
        self.zoom_in_button.pack(side=tk.LEFT)
        
        self.zoom_out_button = tk.Button(self.root, text="Zoom Out", command=lambda: self.zoom(0.8))
        self.zoom_out_button.pack(side=tk.RIGHT)

    def show_image(self, image):
        self.tk_image = ImageTk.PhotoImage(image)
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.tk_image)
        self.canvas.config(scrollregion=self.canvas.bbox(tk.ALL))

    def on_left_click(self, event):
        items = self.canvas.find_overlapping(event.x, event.y, event.x + 1, event.y + 1)
        for item in items:
            if item in self.rectangles:
                self.canvas.delete(item)
                self.rectangles.remove(item)

    def on_right_click(self, event):
        self.start_x = event.x
        self.start_y = event.y
        self.rect = self.canvas.create_rectangle(self.start_x, self.start_y, self.start_x, self.start_y, outline='red')
        self.rectangles.append(self.rect)

    def on_drag(self, event):
        self.canvas.coords(self.rect, self.start_x, self.start_y, event.x, event.y)

    def next_page(self):
        if self.current_image < len(self.images) - 1:
            self.current_image += 1
            self.show_image(self.images[self.current_image])

    def prev_page(self):
        if self.current_image > 0:
            self.current_image -= 1
            self.show_image(self.images[self.current_image])

    def zoom(self, scale):
        image = self.images[self.current_image]
        size = (int(image.width * scale), int(image.height * scale))
        resized_image = image.resize(size, Image.ANTIALIAS)
        self.show_image(resized_image)

def pdf_to_images(pdf_path):
    images = convert_from_path(pdf_path)
    return images

def upload_pdf():
    file_path = filedialog.askopenfilename(filetypes=[("PDF Files", "*.pdf")])
    if file_path:
        images = pdf_to_images(file_path)
        root = tk.Tk()
        app = TableDividerApp(root, images)
        root.mainloop()

if __name__ == "__main__":
    upload_pdf()
