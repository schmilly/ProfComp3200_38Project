from PyQt5.QtWidgets import QWidget, QVBoxLayout, QPushButton, QGraphicsView, QGraphicsScene, QGraphicsRectItem, QFileDialog, QHBoxLayout
from PyQt5.QtGui import QPixmap, QImage, QPen, QColor
from PyQt5.QtCore import Qt, QRectF, QPointF
from PIL import Image
import os

class TableDividerApp(QWidget):
    def __init__(self, images, parent=None):
        super().__init__(parent)
        self.images = images
        self.current_image = 0
        self.rect_coords = []
        self.cell_coords = []
        self.rect_item = None
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # Image display area
        self.scene = QGraphicsScene()
        self.view = QGraphicsView(self.scene)
        layout.addWidget(self.view)

        # Load and display the first image
        self.show_image(self.images[self.current_image])

        # Control buttons
        control_layout = QHBoxLayout()

        self.prev_button = QPushButton("Previous Page", self)
        self.prev_button.clicked.connect(self.prev_page)
        control_layout.addWidget(self.prev_button)

        self.next_button = QPushButton("Next Page", self)
        self.next_button.clicked.connect(self.next_page)
        control_layout.addWidget(self.next_button)

        self.save_button = QPushButton("Save Coordinates", self)
        self.save_button.clicked.connect(self.save_coordinates)
        control_layout.addWidget(self.save_button)

        layout.addLayout(control_layout)

        self.setLayout(layout)

    def show_image(self, image_path):
        # Load image using PIL and convert to QPixmap for display
        image = Image.open(image_path)
        self.qimage = self.pil2pixmap(image)
        self.pixmap_item = self.scene.addPixmap(self.qimage)
        self.view.fitInView(self.pixmap_item, Qt.KeepAspectRatio)

        self.scene.clear()
        self.scene.addPixmap(self.qimage)

    def pil2pixmap(self, image):
        # Convert a PIL Image to QPixmap for use in QGraphicsView
        image = image.convert("RGBA")
        data = image.tobytes("raw", "RGBA")
        qimage = QImage(data, image.width, image.height, QImage.Format_RGBA8888)
        return QPixmap.fromImage(qimage)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            # Store starting position of rectangle
            pos = self.view.mapToScene(event.pos())
            self.rect_coords.append(pos)
            if len(self.rect_coords) == 2:
                self.draw_rectangle()
                self.cell_coords.append(self.rect_coords)
                self.rect_coords = []
        elif event.button() == Qt.RightButton:
            # Reset selection
            self.rect_coords = []
            if self.rect_item:
                self.scene.removeItem(self.rect_item)
            print("Selection reset.")

    def draw_rectangle(self):
        if len(self.rect_coords) == 2:
            # Draw a rectangle on the image
            x1, y1 = self.rect_coords[0].x(), self.rect_coords[0].y()
            x2, y2 = self.rect_coords[1].x(), self.rect_coords[1].y()
            rect = QRectF(QPointF(x1, y1), QPointF(x2, y2))
            self.rect_item = QGraphicsRectItem(rect)
            self.rect_item.setPen(QPen(QColor('red'), 2))
            self.scene.addItem(self.rect_item)
            print(f"Rectangle from ({x1}, {y1}) to ({x2}, {y2})")

    def next_page(self):
        # Navigate to the next image in the list
        if self.current_image < len(self.images) - 1:
            self.current_image += 1
            self.show_image(self.images[self.current_image])

    def prev_page(self):
        # Navigate to the previous image in the list
        if self.current_image > 0:
            self.current_image -= 1
            self.show_image(self.images[self.current_image])

    def save_coordinates(self):
        # Save the coordinates of the drawn rectangles to a text file
        output_file, _ = QFileDialog.getSaveFileName(self, "Save Coordinates", "", "Text Files (*.txt)")
        if output_file:
            with open(output_file, 'w') as file:
                for coords in self.cell_coords:
                    coord_str = f"({coords[0].x()}, {coords[0].y()}) to ({coords[1].x()}, {coords[1].y()})"
                    file.write(coord_str + "\n")
            print(f"Coordinates saved to {output_file}.")
