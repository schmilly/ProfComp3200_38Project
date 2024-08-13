import tkinter as tk
from tkinter import filedialog
from PIL import Image, ImageTk
from pdf2image import convert_from_path

class TableDividerApp:
    def __init__(self, root):
        self.root = root
        self.images = []
        self.current_image = 0
        self.rectangles = []
        self.rect_ids = []  # Track rectangle IDs for easy removal
        self.start_x = None
        self.start_y = None
        self.setup_ui()

    def setup_ui(self):
        self.canvas = tk.Canvas(self.root, width=800, height=600)
        self.canvas.pack()

        self.upload_button = tk.Button(self.root, text="Upload PDF", command=self.upload_pdf)
        self.upload_button.pack()

        self.prev_button = tk.Button(self.root, text="Previous Page", command=self.show_prev_image)
        self.prev_button.pack(side=tk.LEFT)

        self.next_button = tk.Button(self.root, text="Next Page", command=self.show_next_image)
        self.next_button.pack(side=tk.RIGHT)

        self.save_button = tk.Button(self.root, text="Save Tables", command=self.save_tables)
        self.save_button.pack()

        self.canvas.bind("<Button-1>", self.on_click)  # Left-click to draw a rectangle
        self.canvas.bind("<B1-Motion>", self.on_drag)  # Drag with left-click
        self.canvas.bind("<ButtonRelease-1>", self.on_release)  # Release left-click to finish selection
        self.canvas.bind("<Button-3>", self.on_right_click)  # Right-click to remove the last rectangle

    def upload_pdf(self):
        file_path = filedialog.askopenfilename(filetypes=[("PDF files", "*.pdf")])
        if file_path:
            self.images = self.convert_pdf_to_images(file_path)
            self.show_image(self.images[self.current_image])

    def convert_pdf_to_images(self, pdf_path):
        images = convert_from_path(pdf_path)
        return images

    def show_image(self, image):
        self.canvas.delete("all")  # Clear the canvas before showing the new image
        resized_image = self.resize_image_to_fit_canvas(image)
        self.tk_image = ImageTk.PhotoImage(resized_image)
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.tk_image)

    def resize_image_to_fit_canvas(self, image):
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        image_ratio = image.width / image.height
        canvas_ratio = canvas_width / canvas_height

        if image_ratio > canvas_ratio:
            new_width = canvas_width
            new_height = int(new_width / image_ratio)
        else:
            new_height = canvas_height
            new_width = int(new_height * image_ratio)

        return image.resize((new_width, new_height), Image.LANCZOS)

    def show_prev_image(self):
        if self.current_image > 0:
            self.current_image -= 1
            self.show_image(self.images[self.current_image])

    def show_next_image(self):
        if self.current_image < len(self.images) - 1:
            self.current_image += 1
            self.show_image(self.images[self.current_image])

    def on_click(self, event):
        self.start_x = event.x
        self.start_y = event.y
        self.rect = self.canvas.create_rectangle(self.start_x, self.start_y, self.start_x, self.start_y, outline='red')

    def on_drag(self, event):
        self.canvas.coords(self.rect, self.start_x, self.start_y, event.x, event.y)

    def on_release(self, event):
        end_x, end_y = event.x, event.y
        rect_id = self.rect  # Capture the ID of the current rectangle
        self.rect_ids.append(rect_id)  # Store the ID for later removal
        self.rectangles.append((self.start_x, self.start_y, end_x, end_y))
        print(f"Rectangle from ({self.start_x}, {self.start_y}) to ({end_x}, {end_y})")

    def on_right_click(self, event):
        if self.rect_ids:
            rect_id = self.rect_ids.pop()  # Remove the last rectangle ID
            self.canvas.delete(rect_id)  # Delete the rectangle from the canvas
            self.rectangles.pop()  # Remove the last rectangle data from the list
            print("Last rectangle removed.")

    def save_tables(self):
        for idx, (start_x, start_y, end_x, end_y) in enumerate(self.rectangles):
            cropped_image = self.images[self.current_image].crop((start_x, start_y, end_x, end_y))
            cropped_image.save(f'table_{self.current_image}_{idx}.png')
        print("Tables saved.")

if __name__ == "__main__":
    root = tk.Tk()
    app = TableDividerApp(root)
    root.mainloop()
