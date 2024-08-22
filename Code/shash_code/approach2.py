import tkinter as tk
from tkinter import filedialog
from PIL import Image, ImageTk
from pdf2image import convert_from_path

class TableDividerApp:
    def __init__(self, root):
        self.root = root
        self.images = []
        self.current_image = 0
        self.lines = []
        self.horizontal_lines = []
        self.vertical_lines = []
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

        self.canvas.bind("<Button-1>", self.on_left_click)   # Left-click to draw a horizontal line
        self.canvas.bind("<Button-3>", self.on_right_click)  # Right-click to draw a vertical line

    def upload_pdf(self):
        file_path = filedialog.askopenfilename(filetypes=[("PDF files", "*.pdf")])
        if file_path:
            self.images = self.convert_pdf_to_images(file_path)
            self.show_image(self.images[self.current_image])

    def convert_pdf_to_images(self, pdf_path):
        images = convert_from_path(pdf_path)
        return images

    def show_image(self, image):
        self.canvas.delete("all")
        self.lines.clear()
        self.horizontal_lines.clear()
        self.vertical_lines.clear()
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

    def on_left_click(self, event):
        line = self.canvas.create_line(0, event.y, self.canvas.winfo_width(), event.y, fill="red")
        self.horizontal_lines.append(event.y)
        self.lines.append(line)
        self.update_lines()

    def on_right_click(self, event):
        line = self.canvas.create_line(event.x, 0, event.x, self.canvas.winfo_height(), fill="blue")
        self.vertical_lines.append(event.x)
        self.lines.append(line)
        self.update_lines()

    def update_lines(self):
        if len(self.horizontal_lines) >= 2 and len(self.vertical_lines) >= 2:
            top = min(self.horizontal_lines)
            bottom = max(self.horizontal_lines)
            left = min(self.vertical_lines)
            right = max(self.vertical_lines)
            box = (left, top, right, bottom)
            cropped_image = self.images[self.current_image].crop(box)
            cropped_image.save(f'cropped_{self.current_image}.png')
            print(f"Cropped image saved: {box}")

    def save_tables(self):
        for idx, line in enumerate(self.lines):
            self.canvas.delete(line)
        print("Saved all cropped images.")

if __name__ == "__main__":
    root = tk.Tk()
    app = TableDividerApp(root)
    root.mainloop()
