import tkinter as tk
from PIL import Image, ImageTk

class TableDividerApp:
    def __init__(self, root, images):
        self.root = root
        self.images = images
        self.current_image = 0
        self.setup_ui()

    def setup_ui(self):
        self.canvas = tk.Canvas(self.root, width=800, height=600)
        self.canvas.pack()
        
        self.show_image(self.images[self.current_image])

        self.canvas.bind("<Button-1>", self.on_click)

    def show_image(self, image):
        self.tk_image = ImageTk.PhotoImage(image)
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.tk_image)

    def on_click(self, event):
        x, y = event.x, event.y
        print(f"Clicked at: {x}, {y}")
        # Implement logic to divide table based on user clicks

if __name__ == "__main__":
    root = tk.Tk()
    images = pdf_to_images('.pdf') #
    app = TableDividerApp(root, images)
    root.mainloop()
