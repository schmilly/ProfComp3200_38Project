import tkinter as tk
from tkinter import Canvas, Button, messagebox
from PIL import ImageTk, Image

class TableDividerApp:
    def __init__(self, root, images):
        self.root = root
        self.root.title("Manual Table Detection")

        # Store the images (PDF pages)
        self.images = images
        self.current_image_index = 0
        self.rectangles = []  # Store rectangles for each image
        self.canvas_rectangles = []  # Store rectangles drawn on the canvas

        # Set up Canvas for displaying images
        self.canvas = Canvas(root, width=images[0].width(), height=images[0].height())
        self.canvas.pack()

        # Add navigation and action buttons
        self.prev_button = Button(root, text="Previous Page", command=self.previous_page)
        self.prev_button.pack(side=tk.LEFT)
        self.next_button = Button(root, text="Next Page", command=self.next_page)
        self.next_button.pack(side=tk.LEFT)
        self.save_button = Button(root, text="Save Tables", command=self.save_tables)
        self.save_button.pack(side=tk.LEFT)

        # Bind mouse events for drawing rectangles
        self.canvas.bind("<ButtonPress-1>", self.on_button_press)
        self.canvas.bind("<B1-Motion>", self.on_mouse_move)
        self.canvas.bind("<ButtonRelease-1>", self.on_button_release)

        # Initialize variables for rectangle drawing
        self.start_x = None
        self.start_y = None
        self.current_rect = None

        # Display the first image
        self.display_image(self.current_image_index)

    def display_image(self, index):
        """Display the image at the specified index."""
        self.canvas_rectangles.clear()
        self.canvas.delete("all")  # Clear any existing drawings

        self.photo_image = ImageTk.PhotoImage(self.images[index])  # Convert image to a Tkinter-friendly format
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.photo_image)

    def on_button_press(self, event):
        """Handle the event when the mouse button is pressed."""
        self.start_x = event.x
        self.start_y = event.y
        self.current_rect = self.canvas.create_rectangle(self.start_x, self.start_y, self.start_x, self.start_y, outline="red", width=2)

    def on_mouse_move(self, event):
        """Handle the event when the mouse is moved."""
        curX, curY = (event.x, event.y)
        self.canvas.coords(self.current_rect, self.start_x, self.start_y, curX, curY)

    def on_button_release(self, event):
        """Handle the event when the mouse button is released."""
        self.rectangles.append((self.start_x, self.start_y, event.x, event.y))
        self.canvas_rectangles.append(self.current_rect)

    def next_page(self):
        """Go to the next page."""
        if self.current_image_index < len(self.images) - 1:
            self.current_image_index += 1
            self.display_image(self.current_image_index)
        else:
            messagebox.showinfo("End", "This is the last page.")

    def previous_page(self):
        """Go to the previous page."""
        if self.current_image_index > 0:
            self.current_image_index -= 1
            self.display_image(self.current_image_index)
        else:
            messagebox.showinfo("Start", "This is the first page.")

    def save_tables(self):
        """Save the manually detected tables."""
        print(f"Rectangles on current page {self.current_image_index}: {self.rectangles}")
        messagebox.showinfo("Save", "Tables have been saved!")
        self.rectangles.clear()
