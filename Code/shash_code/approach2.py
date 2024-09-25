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
        self.undo_stack = []
        self.zoom_level = 1.0
        self.setup_ui()

    def setup_ui(self):
        self.canvas = tk.Canvas(self.root, width=800, height=600, scrollregion=(0, 0, 800, 1200))
        self.canvas.pack(expand=tk.YES, fill=tk.BOTH)

        # Adding scrollbars
        self.scroll_x = tk.Scrollbar(self.root, orient=tk.HORIZONTAL, command=self.canvas.xview)
        self.scroll_x.pack(side=tk.BOTTOM, fill=tk.X)
        self.scroll_y = tk.Scrollbar(self.root, orient=tk.VERTICAL, command=self.canvas.yview)
        self.scroll_y.pack(side=tk.RIGHT, fill=tk.Y)

        self.canvas.configure(xscrollcommand=self.scroll_x.set, yscrollcommand=self.scroll_y.set)

        # Buttons for functionality
        button_frame = tk.Frame(self.root)
        button_frame.pack(side=tk.BOTTOM, fill=tk.X)

        self.upload_button = tk.Button(button_frame, text="Upload PDF", command=self.upload_pdf)
        self.upload_button.pack(side=tk.LEFT)

        self.prev_button = tk.Button(button_frame, text="Previous Page", command=self.show_prev_image)
        self.prev_button.pack(side=tk.LEFT)

        self.next_button = tk.Button(button_frame, text="Next Page", command=self.show_next_image)
        self.next_button.pack(side=tk.LEFT)

        self.save_button = tk.Button(button_frame, text="Save Tables", command=self.save_tables)
        self.save_button.pack(side=tk.LEFT)

        self.undo_button = tk.Button(button_frame, text="Undo Last Line", command=self.undo_last_line)
        self.undo_button.pack(side=tk.LEFT)

        self.zoom_in_button = tk.Button(button_frame, text="Zoom In", command=self.zoom_in)
        self.zoom_in_button.pack(side=tk.LEFT)

        self.zoom_out_button = tk.Button(button_frame, text="Zoom Out", command=self.zoom_out)
        self.zoom_out_button.pack(side=tk.LEFT)

        self.canvas.bind("<Button-1>", self.draw_vertical_line)  # Left-click for vertical line
        self.canvas.bind("<Button-3>", self.draw_horizontal_line)  # Right-click for horizontal line

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
        self.redraw_lines()  # Redraw lines after showing the image

    def resize_image_to_fit_canvas(self, image):
        canvas_width = int(self.canvas.winfo_width() * self.zoom_level)
        canvas_height = int(self.canvas.winfo_height() * self.zoom_level)
        return image.resize((canvas_width, canvas_height), Image.LANCZOS)

    def show_prev_image(self):
        if self.current_image > 0:
            self.current_image -= 1
            self.show_image(self.images[self.current_image])

    def show_next_image(self):
        if self.current_image < len(self.images) - 1:
            self.current_image += 1
            self.show_image(self.images[self.current_image])

    def draw_horizontal_line(self, event):
        y = event.y / self.zoom_level
        self.horizontal_lines.append(y)
        line = self.canvas.create_line(0, y * self.zoom_level, self.canvas.winfo_width(), y * self.zoom_level, fill="red")
        self.undo_stack.append(("horizontal", line, y))
        self.update_rectangles()

    def draw_vertical_line(self, event):
        x = event.x / self.zoom_level
        self.vertical_lines.append(x)
        line = self.canvas.create_line(x * self.zoom_level, 0, x * self.zoom_level, self.canvas.winfo_height(), fill="blue")
        self.undo_stack.append(("vertical", line, x))
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

    def undo_last_line(self):
        if self.undo_stack:
            line_type, line, pos = self.undo_stack.pop()
            if line_type == "horizontal":
                self.horizontal_lines.remove(pos)
            elif line_type == "vertical":
                self.vertical_lines.remove(pos)
            self.canvas.delete(line)
            self.update_rectangles()

    def zoom_in(self):
        self.zoom_level *= 1.1
        self.show_image(self.images[self.current_image])

    def zoom_out(self):
        self.zoom_level /= 1.1
        self.show_image(self.images[self.current_image])

    def redraw_lines(self):
        for y in self.horizontal_lines:
            self.canvas.create_line(0, y * self.zoom_level, self.canvas.winfo_width(), y * self.zoom_level, fill="red")
        for x in self.vertical_lines:
            self.canvas.create_line(x * self.zoom_level, 0, x * self.zoom_level, self.canvas.winfo_height(), fill="blue")

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
