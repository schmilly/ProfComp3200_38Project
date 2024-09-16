import tkinter as tk
from tkinter import filedialog
from PIL import Image, ImageTk
from pdf2image import convert_from_path

class TableDividerApp:
    def __init__(self, root, file_path):
        self.root = root
        self.images = []
        self.current_image = 0
        self.horizontal_lines = []
        self.vertical_lines = []
        self.rectangles = []
        self.undo_stack = []
        self.setup_ui()
        self.load_pdf(file_path)

    def setup_ui(self):
        self.canvas = tk.Canvas(self.root, width=800, height=600)
        self.canvas.pack()

        # Frame for buttons
        button_frame = tk.Frame(self.root)
        button_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=10)

        self.prev_button = tk.Button(button_frame, text="Previous Page", command=self.show_prev_image)
        self.prev_button.grid(row=0, column=0, padx=5)

        self.upload_button = tk.Button(button_frame, text="Upload PDF", command=self.upload_pdf)
        self.upload_button.grid(row=0, column=1, padx=5)

        self.next_button = tk.Button(button_frame, text="Next Page", command=self.show_next_image)
        self.next_button.grid(row=0, column=2, padx=5)

        self.save_button = tk.Button(button_frame, text="Save Tables", command=self.save_tables)
        self.save_button.grid(row=0, column=3, padx=5)

        self.undo_button = tk.Button(button_frame, text="Undo Last Line", command=self.undo_last_line)
        self.undo_button.grid(row=0, column=4, padx=5)

        self.canvas.bind("<Button-1>", self.draw_horizontal_line)
        self.canvas.bind("<Button-3>", self.draw_vertical_line)

    def upload_pdf(self):
        file_path = filedialog.askopenfilename(filetypes=[("PDF files", "*.pdf")])
        if file_path:
            self.images = self.convert_pdf_to_images(file_path)
            self.show_image(self.images[self.current_image])

    def load_pdf(self, pdf_path):
        self.images = self.convert_pdf_to_images(pdf_path)
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
        line = self.canvas.create_line(0, y, self.canvas.winfo_width(), y, fill="red")
        self.undo_stack.append(("horizontal", line, y))
        self.update_rectangles()

    def draw_vertical_line(self, event):
        x = event.x
        self.vertical_lines.append(x)
        line = self.canvas.create_line(x, 0, x, self.canvas.winfo_height(), fill="blue")
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

# Initial welcome window
def show_welcome_window():
    welcome_window = tk.Toplevel()
    welcome_window.title("Welcome")
    welcome_window.geometry("300x150")

    label = tk.Label(welcome_window, text="Welcome!\nPlease upload a PDF to continue.", font=("Arial", 12))
    label.pack(pady=20)

    upload_button = tk.Button(welcome_window, text="Upload PDF", command=lambda: upload_and_load(welcome_window))
    upload_button.pack(pady=10)

def upload_and_load(welcome_window):
    file_path = filedialog.askopenfilename(filetypes=[("PDF files", "*.pdf")])
    if file_path:
        welcome_window.destroy()
        root = tk.Tk()
        root.title("Table Divider App")
        app = TableDividerApp(root, file_path)
        root.mainloop()

if __name__ == "__main__":
    root = tk.Tk()
    root.withdraw()  # Hide the main window initially
    show_welcome_window()
    root.mainloop()
