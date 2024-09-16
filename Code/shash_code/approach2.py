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
        self.undo_stack = []  # Stack to keep track of drawn lines
        self.setup_ui()

    def setup_ui(self):
        self.canvas = tk.Canvas(self.root, width=800, height=600)
        self.canvas.pack()

        # Upload PDF Button
        self.upload_button = tk.Button(self.root, text="Upload PDF", command=self.upload_pdf)
        self.upload_button.pack()

        # Previous Page Button
        self.prev_button = tk.Button(self.root, text="Previous Page", command=self.show_prev_image)
        self.prev_button.pack(side=tk.LEFT)

        # Next Page Button
        self.next_button = tk.Button(self.root, text="Next Page", command=self.show_next_image)
        self.next_button.pack(side=tk.RIGHT)

        # Save Tables Button
        self.save_button = tk.Button(self.root, text="Save Tables", command=self.save_tables)
        self.save_button.pack()

        # Undo Last Line Button
        self.undo_button = tk.Button(self.root, text="Undo Last Line", command=self.undo_last_line)
        self.undo_button.pack()

        # Bind mouse clicks for drawing lines
        self.canvas.bind("<Button-1>", self.draw_horizontal_line)  # Left-click for horizontal
        self.canvas.bind("<Button-3>", self.draw_vertical_line)    # Right-click for vertical

    def upload_pdf(self):
        # Ask for PDF file
        file_path = filedialog.askopenfilename(filetypes=[("PDF files", "*.pdf")])
        if file_path:
            # Convert PDF to images (one image per page)
            self.images = self.convert_pdf_to_images(file_path)
            # Display the first page
            self.show_image(self.images[self.current_image])

    def convert_pdf_to_images(self, pdf_path):
        # Convert PDF pages to images
        images = convert_from_path(pdf_path)
        return images

    def show_image(self, image):
        # Clear the canvas
        self.canvas.delete("all")

        # Resize the image to fit the canvas
        resized_image = self.resize_image_to_fit_canvas(image)
        self.tk_image = ImageTk.PhotoImage(resized_image)

        # Display the image on the canvas
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.tk_image)

    def resize_image_to_fit_canvas(self, image):
        # Get canvas dimensions
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()

        # Calculate image aspect ratio
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
        # Draw the line
        line = self.canvas.create_line(0, y, self.canvas.winfo_width(), y, fill="red")
        self.horizontal_lines.append(y)
        self.undo_stack.append(("horizontal", line, y))  # Add line to the undo stack
        self.update_rectangles()

    def draw_vertical_line(self, event):
        x = event.x
        # Draw the line
        line = self.canvas.create_line(x, 0, x, self.canvas.winfo_height(), fill="blue")
        self.vertical_lines.append(x)
        self.undo_stack.append(("vertical", line, x))  # Add line to the undo stack
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
            # Get the last drawn line
            line_type, line, pos = self.undo_stack.pop()

            # Remove the line from the corresponding list (horizontal or vertical)
            if line_type == "horizontal":
                self.horizontal_lines.remove(pos)
            elif line_type == "vertical":
                self.vertical_lines.remove(pos)

            # Delete the line from the canvas
            self.canvas.delete(line)
            self.update_rectangles()

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
