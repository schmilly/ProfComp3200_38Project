import tkinter as tk
from tkinter import filedialog
from PIL import Image, ImageTk
from pdf2image import convert_from_path

class TableDividerApp:
    def __init__(self, root):
        self.root = root
        self.images = []
        self.current_image = 0
        self.horizontal_lines = []
        self.vertical_lines = []
        self.rectangles = []
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

        self.canvas.bind("<Button-1>", self.draw_horizontal_line)
        self.canvas.bind("<Button-3>", self.draw_vertical_line)

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

    def draw_horizontal_line(self, event):
        y = event.y
        self.horizontal_lines.append(y)
        self.canvas.create_line(0, y, self.canvas.winfo_width(), y, fill="red")
        self.update_rectangles()

    def draw_vertical_line(self, event):
        x = event.x
        self.vertical_lines.append(x)
        self.canvas.create_line(x, 0, x, self.canvas.winfo_height(), fill="blue")
        self.update_rectangles()

    def update_rectangles(self):
        self.rectangles.clear()
        self.horizontal_lines.sort()
        self.vertical_lines.sort()
        for i in range(len(self.horizontal_lines) - 1):
            for j in range(len(self.vertical_lines) - 1):
                top = self.horizontal_lines[i]
                bottom = self.horizontal_lines[i + 1]
                left = self.vertical_lines[j]
                right = self.vertical_lines[j + 1]
                self.rectangles.append((left, top, right, bottom))

    def save_tables(self):
        for idx, (left, top, right, bottom) in enumerate(self.rectangles):
            left, right = sorted([left, right])
            top, bottom = sorted([top, bottom])
            cropped_image = self.images[self.current_image].crop((left, top, right, bottom))
            cropped_image.save(f'table_{self.current_image}_{idx}.png')
        print(f"{len(self.rectangles)} tables saved.")

if __name__ == "__main__":
    root = tk.Tk()
    app = TableDividerApp(root)
    root.mainloop()
