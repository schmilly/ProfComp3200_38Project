import tkinter as tk
from tkinter import filedialog
from tkinter import ttk  # For adding the scrollbar
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
        self.zoom_factor = 1.0  # For zooming in/out
        self.setup_ui()

    def setup_ui(self):
        self.root.geometry("1000x800")  # Start with a large window

        # Main frame to contain canvas and scrollbars
        main_frame = tk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=1)

        # Canvas with scrollbars
        self.canvas = tk.Canvas(main_frame, bg='grey')
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=1)

        scroll_y = ttk.Scrollbar(main_frame, orient=tk.VERTICAL, command=self.canvas.yview)
        scroll_y.pack(side=tk.RIGHT, fill=tk.Y)

        scroll_x = ttk.Scrollbar(main_frame, orient=tk.HORIZONTAL, command=self.canvas.xview)
        scroll_x.pack(side=tk.BOTTOM, fill=tk.X)

        self.canvas.config(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)
        self.canvas.bind("<Configure>", self.resize_canvas)

        # Frame for buttons
        button_frame = tk.Frame(self.root)
        button_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=10)

        # Align buttons in the frame
        self.upload_button = tk.Button(button_frame, text="Upload PDF", command=self.upload_pdf)
        self.upload_button.grid(row=0, column=1, padx=5)

        self.prev_button = tk.Button(button_frame, text="Previous Page", command=self.show_prev_image)
        self.prev_button.grid(row=0, column=0, padx=5)

        self.next_button = tk.Button(button_frame, text="Next Page", command=self.show_next_image)
        self.next_button.grid(row=0, column=2, padx=5)

        self.save_button = tk.Button(button_frame, text="Save Tables", command=self.save_tables)
        self.save_button.grid(row=0, column=3, padx=5)

        self.undo_button = tk.Button(button_frame, text="Undo Last Line", command=self.undo_last_line)
        self.undo_button.grid(row=0, column=4, padx=5)

        # Add Zoom In and Zoom Out buttons
        self.zoom_in_button = tk.Button(button_frame, text="Zoom In", command=self.zoom_in)
        self.zoom_in_button.grid(row=0, column=5, padx=5)

        self.zoom_out_button = tk.Button(button_frame, text="Zoom Out", command=self.zoom_out)
        self.zoom_out_button.grid(row=0, column=6, padx=5)

        # Bind mouse clicks for drawing lines
        self.canvas.bind("<Button-1>", self.draw_horizontal_line)  # Left-click for horizontal
        self.canvas.bind("<Button-3>", self.draw_vertical_line)    # Right-click for vertical

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
        self.canvas.config(scrollregion=self.canvas.bbox(tk.ALL))  # Set scroll region

    def resize_image_to_fit_canvas(self, image):
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()

        # Apply zoom factor
        new_width = int(image.width * self.zoom_factor)
        new_height = int(image.height * self.zoom_factor)

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
        line = self.canvas.create_line(0, y, self.canvas.winfo_width(), y, fill="red")
        self.horizontal_lines.append(y)
        self.undo_stack.append(("horizontal", line, y))
        self.update_rectangles()

    def draw_vertical_line(self, event):
        x = event.x
        line = self.canvas.create_line(x, 0, x, self.canvas.winfo_height(), fill="blue")
        self.vertical_lines.append(x)
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

    def save_tables(self):
        for idx, (left, top, right, bottom) in enumerate(self.rectangles):
            left, right = sorted([left, right])
            top, bottom = sorted([top, bottom])
            cropped_image = self.images[self.current_image].crop((left, top, right, bottom))
            cropped_image.save(f'table_{self.current_image}_{idx}.png')
        print(f"{len(self.rectangles)} tables saved.")

    def resize_canvas(self, event):
        self.canvas.config(scrollregion=self.canvas.bbox(tk.ALL))

    def zoom_in(self):
        self.zoom_factor *= 1.1
        self.show_image(self.images[self.current_image])

    def zoom_out(self):
        self.zoom_factor *= 0.9
        self.show_image(self.images[self.current_image])

if __name__ == "__main__":
    root = tk.Tk()
    app = TableDividerApp(root)
    root.mainloop()
