# Standard library imports
import sys
import os

from TableDetection import luminositybased
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
from pathlib import Path
import logging
import mimetypes
import threading
import time
import signal
import smtplib
import pickle
import shutil
import csv
import traceback
from email.message import EmailMessage
#from PyPDF2 import PdfFileReader
#import PyPDF2
import json
import paddle
from collections import deque

# Third-party imports
import cv2
import numpy as np
import pandas as pd
import webbrowser
import urllib.parse
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QAction, QFileDialog, QGraphicsView, QGraphicsScene,
    QGraphicsRectItem, QGraphicsLineItem, QVBoxLayout, QHBoxLayout, QWidget, QSplitter, QTextEdit,
    QMenuBar, QMenu, QToolBar, QLabel, QComboBox, QProgressBar, QStatusBar, QTreeWidget, QTreeWidgetItem,
    QPushButton, QMessageBox, QGraphicsPixmapItem, QTableWidget, QTableWidgetItem, QGraphicsObject,
    QDockWidget, QListWidget, QTabWidget, QInputDialog, QWidgetAction, QActionGroup, QTextBrowser, QLineEdit,
    QDialog, QUndoCommand, QGraphicsItem, QHeaderView
)
from PyQt5.QtGui import QPixmap, QImage, QPen, QColor, QPainter, QFont, QDragEnterEvent, QDropEvent, QCursor, QIcon
from PyQt5.QtCore import Qt, QRectF, QObject, pyqtSignal, QLineF, QThread, QPointF, QSizeF
#from pdf2image import convert_from_path
from PIL import Image
from logging.handlers import RotatingFileHandler

import RunThroughTest as ocr_module

class ExcludeMainLoggerFilter(logging.Filter):
    def filter(self, record):
        return record.name != '__main__'

def configure_logging():
    """Configures the logging settings."""
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)  # Capture all levels of logs

    # Formatter for log messages
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # File handler to write logs to a file
    file_handler = RotatingFileHandler('OCR_app.log', maxBytes=5*1024*1024, backupCount=1, encoding='utf-8')    
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Console handler to output logs to the console
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)  # Adjust as needed
    console_handler.setFormatter(formatter)
    # Apply the custom filter to exclude __main__ logger
    console_handler.addFilter(ExcludeMainLoggerFilter())
    logger.addHandler(console_handler)

def exception_hook(exctype, value, tb):
    """Global exception handler to capture and log uncaught exceptions."""
    # Log the exception with traceback
    logging.critical("Uncaught exception", exc_info=(exctype, value, tb))
    
    # Format the traceback
    tb_str = ''.join(traceback.format_exception(exctype, value, tb))
    
    # Show the error message to the user
    QMessageBox.critical(
        None,
        "Critical Error",
        f"An unexpected error occurred:\n\n{tb_str}"
    )
    
    # Exit the application
    sys.exit(1)

sys.excepthook = exception_hook

class EmittingStream(QObject):
    textWritten = pyqtSignal(str)

    def write(self, text):
        text = text.strip()
        if text:
            self.textWritten.emit(str(text + '\n'))

    def flush(self):
        pass

class LineItem(QGraphicsObject):
    moved = pyqtSignal(QLineF, QLineF)  # Signal emitted when the line is moved (old_line, new_line)

    def __init__(self, line, orientation='horizontal', image_filename=None, parent=None):
        """
        Initialize the LineItem.

        Parameters:
            line (QLineF or tuple): Either a QLineF object or a tuple containing (QLineF, orientation).
            orientation (str): 'horizontal' or 'vertical'. Default is 'horizontal'.
            image_filename (str): The filename of the associated image. Default is None.
            parent (QGraphicsObject): The parent graphics object. Default is None.
        """
        super().__init__(parent)
        self.logger = logging.getLogger(__name__)  # Initialize the logger

        # Handle initialization with tuple (line, orientation)
        if isinstance(line, tuple):
            if len(line) != 2:
                self.logger.error("Line tuple must contain exactly two elements: (QLineF, orientation).")
                raise ValueError("Line tuple must contain exactly two elements: (QLineF, orientation).")
            if not isinstance(line[0], QLineF):
                self.logger.error("First element of the tuple must be a QLineF object.")
                raise TypeError("First element of the tuple must be a QLineF object.")
            if line[1] not in ['horizontal', 'vertical']:
                self.logger.error("Orientation must be either 'horizontal' or 'vertical'.")
                raise ValueError("Orientation must be either 'horizontal' or 'vertical'.")
            self._line, self.orientation = line
        else:
            if not isinstance(line, QLineF):
                self.logger.error("Line must be a QLineF object or a tuple of (QLineF, orientation).")
                raise TypeError("Line must be a QLineF object or a tuple of (QLineF, orientation).")
            if orientation not in ['horizontal', 'vertical']:
                self.logger.error("Orientation must be either 'horizontal' or 'vertical'.")
                raise ValueError("Orientation must be either 'horizontal' or 'vertical'.")
            self.orientation = orientation
            self._line = QLineF(line)  # Store the line as an attribute

        self._previous_line = QLineF(self._line)  # Initialize previous_line with the initial line position
        self.image_filename = image_filename  # Associate the line with an image

        # Set up pen for drawing the line
        self._pen = QPen(QColor(0, 0, 255), 2, Qt.SolidLine)  # Blue pen, 2 pixels wide
        self.setPen(self._pen)

        # Enable item flags for interactivity
        self.setFlags(
            QGraphicsObject.ItemIsSelectable |
            QGraphicsObject.ItemIsMovable |
            QGraphicsObject.ItemSendsGeometryChanges
        )
        self.setAcceptHoverEvents(True)

    def boundingRect(self):
        """Define the bounding rectangle for the LineItem."""
        pen_width = self._pen.widthF()
        extra = pen_width / 2.0
        return QRectF(self._line.p1(), self._line.p2()).normalized().adjusted(-extra, -extra, extra, extra)

    def paint(self, painter, option, widget=None):
        """Paint the LineItem using the current pen."""
        try:
            painter.setPen(self._pen)
            painter.drawLine(self._line)
        except Exception as e:
            self.logger.error(f"Error in LineItem paint: {e}", exc_info=True)

    def setPen(self, pen):
        """Set a new pen for the LineItem and update its appearance."""
        self._pen = pen
        self.update()

    @property
    def line(self):
        """Get the current QLineF object."""
        return self._line

    @line.setter
    def line(self, new_line):
        """
        Set a new QLineF object for the LineItem.

        Parameters:
            new_line (QLineF): The new line to set.
        """
        if not isinstance(new_line, QLineF):
            self.logger.error("New line must be a QLineF object.")
            raise TypeError("New line must be a QLineF object.")
        self._line = new_line
        self.update()

    def itemChange(self, change, value):
        """
        Handle changes to the item's state, particularly its position.

        Parameters:
            change (GraphicsItemChange): The type of change.
            value (QVariant): The new value associated with the change.

        Returns:
            QVariant: The value to be applied.
        """
        if change == QGraphicsObject.ItemPositionChange:
            # Calculate the movement delta
            new_pos = value
            delta = new_pos - self.pos()

            # Depending on orientation, adjust the line's position
            if self.orientation == 'horizontal':
                # Move only vertically
                new_line = QLineF(
                    self._line.p1().x(),
                    self._line.p1().y() + delta.y(),
                    self._line.p2().x(),
                    self._line.p2().y() + delta.y()
                )
                # Prevent horizontal movement by resetting the x position
                new_pos.setX(self.pos().x())
            elif self.orientation == 'vertical':
                # Move only horizontally
                new_line = QLineF(
                    self._line.p1().x() + delta.x(),
                    self._line.p1().y(),
                    self._line.p2().x() + delta.x(),
                    self._line.p2().y()
                )
                # Prevent vertical movement by resetting the y position
                new_pos.setY(self.pos().y())
            else:
                # Allow free movement
                new_line = QLineF(
                    self._line.p1().x() + delta.x(),
                    self._line.p1().y() + delta.y(),
                    self._line.p2().x() + delta.x(),
                    self._line.p2().y() + delta.y()
                )

            # Emit the moved signal with old and new lines
            self.moved.emit(QLineF(self._previous_line), QLineF(new_line))

            # Update the line and previous_line
            self._line = new_line
            self._previous_line = QLineF(new_line)
            self.update()

            return new_pos
        return super().itemChange(change, value)

class RectItem(QGraphicsObject):
    moved = pyqtSignal(QRectF)  # Signal emitted when the rectangle is moved

    def __init__(self, rect, parent=None, image_filename=None):
        super().__init__(parent)
        self.logger = logging.getLogger(__name__) 
        self._rect = QRectF(rect)
        self._pen = QPen(QColor(255, 0, 0), 2)  # Red pen, 2 pixels wide
        self.setPen(self._pen)
        self.setFlags(
            QGraphicsObject.ItemIsSelectable |
            QGraphicsObject.ItemIsMovable |
            QGraphicsObject.ItemSendsGeometryChanges
        )
        self.setAcceptHoverEvents(True)
        self.image_filename = image_filename  # Associate the rectangle with an image

    def boundingRect(self):
        pen_width = self._pen.widthF()
        extra = pen_width / 2.0
        return self._rect.normalized().adjusted(-extra, -extra, extra, extra)

    def paint(self, painter, option, widget=None):
        try:
            painter.setPen(self._pen)
            painter.drawRect(self._rect)
        except Exception as e:
            self.logger.error(f"Error in RectItem paint: {e}", exc_info=True)

    def setPen(self, pen):
        self._pen = pen
        self.update()

    @property
    def rect(self):
        return self._rect

    @rect.setter
    def rect(self, new_rect):
        self.prepareGeometryChange()
        self._rect = QRectF(new_rect)
        self.update()

    def itemChange(self, change, value):
        if change == QGraphicsObject.ItemPositionChange:
            # Calculate the movement delta
            new_pos = value
            delta = new_pos - self.pos()

            # Update the rectangle position
            new_rect = self._rect.translated(delta)
            self.rect = new_rect  # Use the setter to update

            # Emit the moved signal with the new rectangle
            self.moved.emit(QRectF(new_rect))

            return new_pos  # Allow the position change
        return super().itemChange(change, value)

class Action:
    """Base class for actions that can be undone/redone."""
    def undo(self):
        pass

    def redo(self):
        pass

class AddLineAction(QUndoCommand):
    def __init__(self, app, line_item):
        super().__init__("Add Line")
        self.app = app
        self.line_item = line_item

    def undo(self):
        self.app.graphics_view.scene().removeItem(self.line_item)
        self.app.graphics_view._line_items.remove(self.line_item)
        self.app.logger.info("Undo add: Line removed.")

    def redo(self):
        self.app.graphics_view.scene().addItem(self.line_item)
        self.app.graphics_view._line_items.append(self.line_item)
        self.app.logger.info("Redo add: Line added.")

class AddRectangleAction(QUndoCommand):
    def __init__(self, view, rect_item):
        super().__init__("Add Rectangle")
        self.view = view
        self.rect_item = rect_item

    def undo(self):
        self.view.scene().removeItem(self.rect_item)
        self.view._rect_items.remove(self.rect_item)
        self.view.lines.pop(self.rect_item.image_filename, None)
        self.view.logger.info("Undo add: Rectangle removed.")

    def redo(self):
        self.view.scene().addItem(self.rect_item)
        self.view._rect_items.append(self.rect_item)
        if self.rect_item.image_filename:
            if self.rect_item.image_filename not in self.view.lines:
                self.view.lines[self.rect_item.image_filename] = []
            # Optionally, store rectangle details if needed
        self.view.logger.info("Redo add: Rectangle added.")

class RemoveLineAction:
    """Represents an undoable action for removing a line."""
    def __init__(self, app, line_item):
        self.app = app
        self.line_item = line_item
        self.key = f"{self.app.graphics_view.current_page_index}_full"

    def undo(self):
        self.app.graphics_view.scene().addItem(self.line_item)
        if self.key not in self.app.lines:
            self.app.lines[self.key] = []
        self.app.lines[self.key].append(self.line_item.line())
        self.app.lineModified.emit()

    def redo(self):
        self.app.graphics_view.scene().removeItem(self.line_item)
        if self.key in self.app.lines:
            try:
                self.app.lines[self.key].remove(self.line_item.line())
            except ValueError:
                self.app.logger.warning(f"Line {self.line_item.line()} not found in lines[{self.key}].")
        self.app.lineModified.emit()

class RemoveRectangleAction(Action):
    def __init__(self, view, rect_item):
        self.view = view
        self.rect_item = rect_item

    def undo(self):
        self.view.scene().addItem(self.rect_item)
        self.view._rect_items.append(self.rect_item)

    def redo(self):
        self.view.scene().removeItem(self.rect_item)
        self.view._rect_items.remove(self.rect_item)

class MoveRectangleAction(QUndoCommand):
    def __init__(self, app, rect_item, old_rect, new_rect):
        super().__init__("Move Rectangle")
        self.app = app
        self.rect_item = rect_item
        self.old_rect = old_rect
        self.new_rect = new_rect

    def undo(self):
        self.rect_item.setRect(self.old_rect)
        self.app.logger.info(f"Undo move: Rectangle reverted to {self.old_rect}")
        self.app.lineModified.emit()

    def redo(self):
        self.rect_item.setRect(self.new_rect)
        self.app.logger.info(f"Redo move: Rectangle moved to {self.new_rect}")
        self.app.lineModified.emit()

class MoveLineAction(QUndoCommand):
    def __init__(self, app, line_item, old_line, new_line):
        super().__init__("Move Line")
        self.app = app
        self.line_item = line_item
        self.old_line = old_line
        self.new_line = new_line

    def undo(self):
        self.line_item.line = self.old_line
        self.line_item.update()
        self.app.logger.info(f"Undo move: Line reverted to {self.old_line}")
        self.app.graphics_view.lineModified.emit()

    def redo(self):
        self.line_item.setLine(self.new_line)
        self.app.logger.info(f"Redo move: Line moved to {self.new_line}")
        self.app.graphics_view.lineModified.emit()

class AddCroppedImageAction(QUndoCommand):
    def __init__(self, app, cropped_image_path, page_index, cropped_index, rect_item):
        super().__init__("Add Cropped Image")
        self.app = app
        self.cropped_image_path = cropped_image_path
        self.page_index = page_index
        self.cropped_index = cropped_index
        self.rect_item = rect_item

    def undo(self):
        try:
            # Remove the cropped image from internal structures
            self.app.cropped_images[self.page_index].remove(self.cropped_image_path)
            
            # Remove from project list
            parent_item = self.app.project_list.topLevelItem(self.page_index)
            for i in range(parent_item.childCount()):
                child = parent_item.child(i)
                if child.text(0).endswith(os.path.basename(self.cropped_image_path)):
                    parent_item.removeChild(child)
                    break

            # Remove the rectangle from the scene
            self.app.graphics_view.scene().removeItem(self.rect_item)
            
            self.app.logger.info(f"Undo: Removed cropped image {self.cropped_image_path} and corresponding rectangle.")
        except Exception as e:
            self.app.logger.error(f"Error undoing cropped image: {e}", exc_info=True)

    def redo(self):
        try:
            # Re-add the cropped image to internal structures
            self.app.cropped_images[self.page_index].append(self.cropped_image_path)
            
            # Re-add to project list
            parent_item = self.app.project_list.topLevelItem(self.page_index)
            cropped_item_text = f"Cropped {self.cropped_index}: {os.path.basename(self.cropped_image_path)}"
            cropped_item = QTreeWidgetItem(parent_item)
            cropped_item.setText(0, cropped_item_text)
            cropped_item.setFlags(cropped_item.flags() | Qt.ItemIsSelectable | Qt.ItemIsEnabled)
            parent_item.addChild(cropped_item)
            parent_item.setExpanded(True)

            # Re-add the rectangle to the scene
            self.app.graphics_view.scene().addItem(self.rect_item)
            
            self.app.logger.info(f"Redo: Re-added cropped image {self.cropped_image_path} and corresponding rectangle.")
        except Exception as e:
            self.app.logger.error(f"Error redoing cropped image: {e}", exc_info=True)

class OcrGui(QObject):
    ocr_progress = pyqtSignal(int, int)
    ocr_completed = pyqtSignal(tuple)
    ocr_error = pyqtSignal(str)

class PageSelectionDialog(QDialog):
    def __init__(self, parent=None, total_pages=0):
        super().__init__(parent)
        self.setWindowTitle("Select Pages for OCR")

        self.total_pages = total_pages

        # Create widgets
        self.label = QLabel(f"Enter page numbers or ranges (1-{self.total_pages}), separated by commas:")
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("e.g., 1, 3-5, 7")

        # OK and Cancel buttons
        self.ok_button = QPushButton("OK")
        self.cancel_button = QPushButton("Cancel")
        self.ok_button.clicked.connect(self.accept)
        self.cancel_button.clicked.connect(self.reject)

        # Layout
        button_layout = QHBoxLayout()
        button_layout.addWidget(self.ok_button)
        button_layout.addWidget(self.cancel_button)

        main_layout = QVBoxLayout()
        main_layout.addWidget(self.label)
        main_layout.addWidget(self.input_field)
        main_layout.addLayout(button_layout)

        self.setLayout(main_layout)

    def get_selected_pages(self):
        return self.input_field.text()

class OCRWorker(QThread):
    ocr_progress = pyqtSignal(int, int)
    ocr_time_estimate = pyqtSignal(float)
    ocr_completed = pyqtSignal(object)
    ocr_error = pyqtSignal(str)

    def __init__(self, pdf_file, storedir, output_csv, ocr_cancel_event, ocr_engine, easyocr_engine, user_lines=None, image_list=None):
        super().__init__()
        self.pdf_file = pdf_file
        self.storedir = storedir
        self.output_csv = output_csv
        self.ocr_cancel_event = ocr_cancel_event
        self.ocr_engine = ocr_engine
        self.easyocr_engine = easyocr_engine
        self.user_lines = user_lines if user_lines else {}
        self.image_list = image_list  # List of images to process
        self.logger = logging.getLogger(self.__class__.__name__)
        self.cell_times = deque(maxlen=20)

    def run(self):
        try:
            self.logger.info("OCR process started.")
            start_time = time.time()
    
            # Validate paths
            if not self.pdf_file or not os.path.exists(self.pdf_file):
                raise ValueError("Invalid or missing PDF file path.")
            if not self.storedir or not os.path.exists(self.storedir):
                raise ValueError("Invalid or missing storage directory.")
            output_dir = os.path.dirname(self.output_csv)
            os.makedirs(output_dir, exist_ok=True)
    
            # Use the existing image list passed from the GUI
            image_list = self.image_list
            if self.ocr_cancel_event.is_set():
                self.emit_cancellation()
    
            # Detect tables in images
            self.logger.info("Detecting tables in images.")
            auto_TableMap = ocr_module.detect_tables_in_images(image_list)
            if self.ocr_cancel_event.is_set():
                self.emit_cancellation()
    
            # Ensure auto_TableMap is a list with correct length
            if isinstance(auto_TableMap, dict):
                auto_TableMap = [auto_TableMap.get(image, [[], []]) for image in image_list]
            elif not (isinstance(auto_TableMap, list) and len(auto_TableMap) == len(image_list)):
                raise ValueError("Mismatch between number of images and detected table maps.")
    
            # Merge user-added lines
            self.logger.info("Incorporating user-added lines into table detection.")
            combined_TableMap = self._merge_user_lines(auto_TableMap, image_list)
    
            if self.ocr_cancel_event.is_set():
                self.emit_cancellation()
    
            # Validate combined_TableMap
            for idx, (columns, rows) in enumerate(combined_TableMap):
                if not (isinstance(columns, list) and isinstance(rows, list)):
                    raise ValueError(f"Invalid table structure for image {image_list[idx]} at index {idx}.")
                if len(columns) < 2 or len(rows) < 2:
                    raise ValueError(f"Insufficient number of columns or rows for image {image_list[idx]} at index {idx}.")
    
            # Cellularize images
            self.logger.info("Cellularizing images based on combined table detection.")
            locationlists = ocr_module.cellularize_images(image_list, combined_TableMap)
            if self.ocr_cancel_event.is_set():
                self.emit_cancellation()
    
            # Flatten the list of image filenames
            all_filenames = [filename for collection in locationlists for filename in collection]
            total_images = len(all_filenames)
            self.logger.info(f"Total cell images to process: {total_images}")
    
            if not all_filenames:
                raise ValueError("No cell images found for OCR processing.")
    
            # Initialize cumulative time
            self.cumulative_time = 0
    
            # Define progress callback function
            def progress_callback(idx, total_images, remaining_time):
                if self.ocr_cancel_event.is_set():
                    self.emit_cancellation()
                # Emit progress and remaining time less frequently
                if idx % 10 == 0 or idx == total_images:
                    self.ocr_progress.emit(idx, total_images)
                    self.ocr_time_estimate.emit(remaining_time)
    
            # OCR Processing using process_all_images
            self.logger.info("Starting OCR processing on cell images.")
    
            # Start timing
            ocr_start_time = time.time()
    
            results = ocr_module.process_all_images(
                all_filenames,
                self.ocr_engine,
                self.easyocr_engine,
                progress_callback=progress_callback
            )
    
            # End timing
            ocr_end_time = time.time()
            self.logger.info(f"OCR processing completed in {ocr_end_time - ocr_start_time:.2f} seconds.")
    
            if self.ocr_cancel_event.is_set():
                self.emit_cancellation()
    
            # Process OCR results
            self.logger.info("Processing OCR results.")
            table_data, total, bad, easyocr_count, paddleocr_count, low_confidence_results = ocr_module.process_results(results)
    
            # Write to CSV
            self.logger.info(f"Writing OCR results to CSV: {self.output_csv}")
            ocr_module.write_results_to_csv(table_data, self.output_csv)
            processing_time = time.time() - start_time
    
            # Emit completion signal with the results and processing time
            self.ocr_completed.emit((table_data, total, bad, easyocr_count, paddleocr_count, low_confidence_results, processing_time))
    
            self.logger.info("OCR process completed successfully.")
            self.logger.info(f"Total OCR processing time: {processing_time:.2f} seconds.")
    
        except Exception as e:
            self.logger.error(f"OCR process failed: {e}", exc_info=True)
            self.ocr_error.emit(f"Critical error: {e}")
    

    def _merge_user_lines(self, auto_TableMap, user_lines, image_list):
        """
        Merges manual lines with automatically detected lines.

        :param auto_TableMap: List of [auto_horizontal, auto_vertical] for each image.
        :param user_lines: Dictionary mapping image filenames to manual lines.
        :param image_list: List of image file paths.
        :return: List of [combined_horizontal, combined_vertical] for each image.
        """
        combined_TableMap = []
        for image_path, auto_map in zip(image_list, auto_TableMap):
            image_filename = os.path.basename(image_path)
            manual = user_lines.get(image_filename, {'horizontal': [], 'vertical': []})
            
            # Merge horizontal lines
            combined_horizontal = auto_map[0] + manual['horizontal']
            combined_horizontal = sorted(set(combined_horizontal))
            
            # Merge vertical lines
            combined_vertical = auto_map[1] + manual['vertical']
            combined_vertical = sorted(set(combined_vertical))
            
            combined_TableMap.append([combined_horizontal, combined_vertical])
            
            self.logger.debug(
                f"Merged {len(manual['horizontal'])} manual horizontal and {len(manual['vertical'])} manual vertical "
                f"lines with {len(auto_map[0])} auto horizontal and {len(auto_map[1])} auto vertical lines for image {image_filename}."
            )
        
        return combined_TableMap

    # def _merge_user_lines(self, auto_TableMap, image_list):
    #     combined_TableMap = []
        
    #     # Log the complete user lines for debugging
    #     self.logger.debug(f"Complete user_lines: {self.user_lines}")
        
    #     for image_path, auto_map in zip(image_list, auto_TableMap):
    #         # Extract just the base filename (without the directory path)
    #         image_filename = os.path.basename(image_path)
            
    #         # Get user lines corresponding to the image filename
    #         user_lines = self.user_lines.get(image_filename, [])
            
    #         # Separate user lines into columns (vertical) and rows (horizontal)
    #         user_columns = [line for line, orientation in user_lines if orientation == 'vertical']
    #         user_rows = [line for line, orientation in user_lines if orientation == 'horizontal']
            
    #         # Convert QLineF objects into tuples (x1, y1, x2, y2) and ensure proper ordering
    #         user_columns = [
    #             (min(line.x1(), line.x2()), min(line.y1(), line.y2()), max(line.x1(), line.x2()), max(line.y1(), line.y2())) 
    #             for line in user_columns
    #         ]
    #         user_rows = [
    #             (min(line.x1(), line.x2()), min(line.y1(), line.y2()), max(line.x1(), line.x2()), max(line.y1(), line.y2())) 
    #             for line in user_rows
    #         ]

    #         # Validate and correct invalid cropping coordinates
    #         def validate_crop_coordinates(col, row):
    #             left, upper, right, lower = col[0], row[0], col[2], row[2]
    #             if left > right or upper > lower:
    #                 self.logger.error(f"Invalid coordinates found: {left, upper, right, lower}. Fixing.")
    #                 left, right = min(left, right), max(left, right)
    #                 upper, lower = min(upper, lower), max(upper, lower)
    #             return (left, upper, right, lower)

    #         # Ensure coordinates are correctly ordered for cropping
    #         combined_columns = [
    #             validate_crop_coordinates(col, row) 
    #             for col in user_columns for row in user_rows
    #         ]
    #         combined_rows = auto_map[1] + user_rows  # Make sure combined_rows is assigned here

    #         # Add the combined table map for this image
    #         combined_TableMap.append([combined_columns, combined_rows])
            
    #         # Log the details for debugging
    #         self.logger.debug(
    #             f"Merged {len(user_columns)} user columns and {len(user_rows)} user rows "
    #             f"with {len(auto_map[0])} auto columns and {len(auto_map[1])} auto rows for image {image_filename}."
    #         )
        
    #     # Return the combined table map
    #     return combined_TableMap

    def emit_cancellation(self):
        """Emits an OCR cancellation signal and stops processing."""
        self.logger.info("OCR process cancelled by user.")
        self.ocr_error.emit("OCR process was cancelled by the user.")
        self.quit()

class PDFGraphicsView(QGraphicsView):
    rectangleSelected = pyqtSignal(QRectF)
    lineModified = pyqtSignal()
    croppedImageCreated = pyqtSignal(int, int, str)
    logger = logging.getLogger(__name__)

    def __init__(self, parent=None):
        super().__init__(parent)
        # Initialize the scene
        self.setScene(QGraphicsScene(self))
        self._start_pos = None
        self._current_rect_item = None
        self.undo_stack = []
        self.redo_stack = []
        self._rect_items = []
        self._line_items = []
        self.cropped_areas = []
        self.pdf_images = []  # Store PDF pages as QImages
        self.current_page_index = 0  # Track the current page
        self.setRenderHint(QPainter.Antialiasing)
        self.setMouseTracking(True)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.cropping_mode = False
        self.adding_vertical_line = False
        self.adding_horizontal_line = False
        self.manual_table_detection_mode = False
        self.lines = {}  # Dictionary to store lines with image filenames as keys
        self.current_image_filename = None
        self.main_window = None
        self.image_file_paths = []  # List to store image file paths

        try:
            self.rectangleSelected.connect(self.get_main_window().on_rectangle_selected)
            self.lineModified.connect(self.get_main_window().on_line_modified)
        except Exception as e:
            self.logger.error(f"Error connecting signals: {e}")

    def set_main_window(self, main_window):
        """Set the reference to the main window."""
        self.main_window = main_window

    def get_main_window(self):
        """Retrieve the main window instance."""
        if self.main_window:
            return self.main_window
        else:
            parent = self.parent()
            while parent is not None:
                if isinstance(parent, QMainWindow):
                    self.main_window = parent  # Cache the main window for future calls
                    return parent
                parent = parent.parent()
            self.logger.error("Main window not found.")
            return None
        
    def get_lines_for_image(self, image_filename):
        """Retrieve lines associated with a specific image filename."""
        return self.lines.get(image_filename, [])

    def get_all_lines(self):
        """Retrieve all lines for all images."""
        return self.lines.copy()

    def enable_manual_table_detection(self, enabled):
        """Enable or disable manual table detection mode."""
        self.manual_table_detection_mode = enabled
        if enabled:
            self.setDragMode(QGraphicsView.NoDrag)
            self.status_bar_message("Manual Table Detection Mode: Add or move lines and rectangles.")
        else:
            self.setDragMode(QGraphicsView.ScrollHandDrag)
            self.status_bar_message("Manual Table Detection Mode Disabled.")

    def toggle_add_vertical_line_mode(self, enabled):
        """Enable or disable vertical line addition mode."""
        self.adding_vertical_line = enabled
        if enabled:
            self.adding_horizontal_line = False
            self.logger.info("Vertical Line Mode activated.")
            self.status_bar_message("Vertical Line Mode: Click on the image to add a vertical line.")
        else:
            self.logger.info("Vertical Line Mode deactivated.")
            self.status_bar_message("Vertical Line Mode Disabled.")

    def toggle_add_horizontal_line_mode(self, enabled):
        """Enable or disable horizontal line addition mode."""
        self.adding_horizontal_line = enabled
        if enabled:
            self.adding_vertical_line = False
            self.logger.info("Horizontal Line Mode activated.")
            self.status_bar_message("Horizontal Line Mode: Click on the image to add a horizontal line.")
        else:
            self.logger.info("Horizontal Line Mode deactivated.")
            self.status_bar_message("Horizontal Line Mode Disabled.")

    def show_error_message(self, message):
        """Displays an error message to the user."""
        QMessageBox.critical(self, "Error", message)
        self.logger.error(f"Error displayed: {message}")

    def set_current_image_filename(self, filename):
        """Set the current image filename."""
        self.current_image_filename = filename

    def get_current_image_filename(self):
        """Retrieve the basename of the currently loaded image."""
        if self.current_image_filename:
            return os.path.basename(self.current_image_filename)
        else:
            self.logger.error("Current image filename is not set.")
            return None
        
    def add_line(self, start_point, end_point, orientation=None):
        """
        Add a straight line from start_point to end_point, extending from edge to edge.
        
        :param start_point: QPointF indicating the start of the line.
        :param end_point: QPointF indicating the end of the line.
        :param orientation: 'horizontal' or 'vertical'. If None, determined automatically.
        """
        try:
            # Determine orientation if not specified
            if orientation is None:
                if start_point.x() == end_point.x():
                    orientation = 'vertical'
                elif start_point.y() == end_point.y():
                    orientation = 'horizontal'
                else:
                    delta_x = abs(end_point.x() - start_point.x())
                    delta_y = abs(end_point.y() - start_point.y())
                    orientation = 'horizontal' if delta_x > delta_y else 'vertical'

            # Get the boundaries of the image
            if hasattr(self, '_pixmap_item') and self._pixmap_item:
                pixmap_rect = self._pixmap_item.pixmap().rect()
            else:
                pixmap_rect = self.sceneRect()

            # Extend the line to edge based on orientation
            if orientation == 'vertical':
                x = start_point.x()
                start_point = QPointF(x, pixmap_rect.top())
                end_point = QPointF(x, pixmap_rect.bottom())
            elif orientation == 'horizontal':
                y = start_point.y()
                start_point = QPointF(pixmap_rect.left(), y)
                end_point = QPointF(pixmap_rect.right(), y)

            # Create the QLineF object
            line = QLineF(start_point, end_point)

            # Create a LineItem (assumes LineItem is a subclass of QGraphicsLineItem with a 'moved' signal)
            line_item = LineItem(line, orientation=orientation)
            self.scene().addItem(line_item)
            self._line_items.append(line_item)

            # Connect the moved signal to handle line movements
            line_item.moved.connect(lambda new_line, item=line_item: self.on_line_moved(item, new_line))

            # Retrieve the main window instance
            main_window = self.get_main_window()
            if main_window:
                # Get current image filename (ensure it returns the base filename)
                current_image_filename = self.get_current_image_filename()
                if not current_image_filename:
                    self.logger.error("Current image filename not found. Cannot associate line with image.")
                    self.show_error_message("Internal Error: Current image not found.")
                    return

                # Initialize the list for the current image if not present
                if current_image_filename not in self.lines:
                    self.lines[current_image_filename] = []

                # Append the new line to the lines dictionary
                self.lines[current_image_filename].append((QLineF(line), orientation))  # Ensure a copy is stored

                # Create and push AddLineAction to undo stack
                action = AddLineAction(main_window, line_item)
                self.undo_stack.append(action)
                self.redo_stack.clear()
                self.lineModified.emit()

                # Save user lines with consistent mapping
                self.save_user_lines(self.current_page_index, self.lines[current_image_filename])

                self.logger.info(f"Line added from {start_point} to {end_point}, Orientation: {orientation}")
            else:
                self.logger.error("Main window instance not found. Cannot add line.")
                self.show_error_message("Internal Error: Main window not found.")
        except Exception as e:
            self.logger.error(f"Error adding line: {e}", exc_info=True)
            main_window = self.get_main_window()
            if main_window:
                main_window.show_error_message(f"Failed to add line: {e}")

    def remove_line(self, line_item):
        """
        Remove a specified line_item.
        
        :param line_item: LineItem object to be removed.
        """
        try:
            if line_item in self._line_items:
                main_window = self.get_main_window()
                if main_window:
                    # Remove the line from the scene and internal list
                    self.scene().removeItem(line_item)
                    self._line_items.remove(line_item)

                    # Remove the line from the lines dictionary
                    image_filename = getattr(line_item, 'image_filename', None)
                    if image_filename and image_filename in self.lines:
                        line_tuple = (line_item.line, line_item.orientation)
                        try:
                            self.lines[image_filename].remove(line_tuple)
                            if not self.lines[image_filename]:
                                del self.lines[image_filename]
                        except ValueError:
                            self.logger.warning(f"Line {line_tuple} not found in lines[{image_filename}].")

                    # Create and push RemoveLineAction to undo stack
                    action = RemoveLineAction(main_window, line_item)
                    self.undo_stack.append(action)
                    self.redo_stack.clear()  # Clear redo stack on new action

                    self.lineModified.emit()

                    # Save updated user lines
                    self.save_user_lines(self.current_page_index, self.lines.get(image_filename, []))

                    self.logger.info("Line removed successfully.")
                else:
                    self.logger.error("Main window instance not found. Cannot remove line.")
                    self.show_error_message("Internal Error: Main window not found.")
            else:
                self.logger.warning("Attempted to remove a non-existent line.")
        except Exception as e:
            self.logger.error(f"Error removing line: {e}", exc_info=True)
            main_window = self.get_main_window()
            if main_window:
                main_window.show_error_message(f"Failed to remove line: {e}")

    def save_user_lines(self, image_filename, lines):
        """Save user-added lines with image filename as the key."""
        try:
            if not image_filename:
                self.logger.error("Image filename is empty. Cannot save user lines.")
                return
            if not os.path.exists(os.path.join(self.image_file_paths[self.current_page_index])):
                self.logger.error(f"Image file does not exist: {self.image_file_paths[self.current_page_index]}")
                return
            self.lines[image_filename] = lines
            self.logger.info(f"Lines saved for {image_filename} with orientations.")
        except Exception as e:
            self.logger.error(f"Error in save_user_lines: {e}", exc_info=True)
            main_window = self.get_main_window()
            if main_window:
                main_window.show_error_message(f"Failed to save user lines: {e}")

    def add_rectangle(self, rect):
        """Add a RectItem to the scene."""
        try:
            # Create a RectItem with the specified rectangle and associate it with the current image
            current_image_filename = self.get_current_image_filename()
            if not current_image_filename:
                self.logger.error("Current image filename not found. Cannot associate rectangle with image.")
                self.show_error_message("Internal Error: Current image not found.")
                return

            rect_item = RectItem(rect, image_filename=current_image_filename)
            self.scene().addItem(rect_item)
            self._rect_items.append(rect_item)

            # Connect the moved signal
            rect_item.moved.connect(lambda new_rect, item=rect_item: self.on_rect_moved(item, new_rect))

            # Create and push AddRectangleAction to undo stack
            action = AddRectangleAction(self, rect_item)
            self.undo_stack.append(action)
            self.redo_stack.clear()  # Clear redo stack on new action

            self.lineModified.emit()

            # Save user lines with consistent mapping (rectangles might not be lines; adjust as needed)
            # Example: If rectangles are part of table detection, you might need to store them separately
            self.save_user_lines(self.current_page_index, self.lines.get(current_image_filename, []))

            self.logger.info(f"Rectangle added: {rect}")
        except Exception as e:
            self.logger.error(f"Error adding rectangle: {e}", exc_info=True)
            self.show_error_message(f"Failed to add rectangle: {e}")

    def on_rect_moved(self, rect_item, new_rect):
        """Handle the movement of a RectItem."""
        try:
            # Capture the previous rectangle position
            previous_rect = rect_item.rect()

            # Create MoveRectangleAction for undo functionality
            action = MoveRectangleAction(self, rect_item, previous_rect, new_rect)
            self.undo_stack.append(action)
            self.redo_stack.clear()
            self.lineModified.emit()
            self.logger.info(f"Rectangle moved from {previous_rect} to {new_rect}")

            # Update the lines dictionary if rectangles are part of it
            image_filename = rect_item.image_filename
            if image_filename and image_filename in self.lines:
                try:
                    # Remove the old rectangle
                    self.lines[image_filename].remove(previous_rect)
                    # Add the new rectangle
                    self.lines[image_filename].append(new_rect)
                    self.logger.debug(f"Updated rectangles for {image_filename}: {self.lines[image_filename]}")
                    # Save the updated user lines
                    self.save_user_lines(self.current_page_index, self.lines[image_filename])
                except ValueError:
                    self.logger.warning(f"Rectangle {previous_rect} not found in lines[{image_filename}].")
        except Exception as e:
            self.logger.error(f"Error handling rectangle movement: {e}", exc_info=True)
            self.show_error_message(f"Failed to move rectangle: {e}")

    def remove_rectangle(self, rect_item):
        """Remove a specified rectangle_item."""
        try:
            if rect_item in self._rect_items:
                self.scene().removeItem(rect_item)
                self._rect_items.remove(rect_item)

                # Create and push RemoveRectangleAction to undo stack
                action = RemoveRectangleAction(self, rect_item)
                self.undo_stack.append(action)
                self.redo_stack.clear()  # Clear redo stack on new action

                self.lineModified.emit()

                # Update the lines dictionary
                image_filename = rect_item.image_filename
                if image_filename and image_filename in self.lines:
                    try:
                        # Remove the rectangle from lines
                        rect_tuple = rect_item.rect()
                        self.lines[image_filename].remove(rect_tuple)
                        if not self.lines[image_filename]:
                            del self.lines[image_filename]
                        # Save the updated user lines
                        self.save_user_lines(self.current_page_index, self.lines.get(image_filename, []))
                    except ValueError:
                        self.logger.warning(f"Rectangle {rect_tuple} not found in lines[{image_filename}].")

                self.logger.info("Rectangle removed.")
            else:
                self.logger.warning("Attempted to remove a non-existent rectangle.")
        except Exception as e:
            self.logger.error(f"Error removing rectangle: {e}", exc_info=True)
            main_window = self.get_main_window()
            if main_window:
                main_window.show_error_message(f"Failed to remove rectangle: {e}")

    def load_image(self, image, filename=None):
        """Load and display the given image in the graphics view."""
        try:
            # Clear existing scene items
            self.scene().clear()
            self._rect_items = []
            self._line_items = []

            # Load image as pixmap
            if isinstance(image, QImage):
                pixmap = QPixmap.fromImage(image)
            elif isinstance(image, QPixmap):
                pixmap = image
            else:
                self.logger.error("Invalid image type passed to load_image.")
                self._image_loaded = False
                self._pixmap_item = None
                return

            # Add pixmap to the scene
            self._pixmap_item = self.scene().addPixmap(pixmap)
            self.scene().setSceneRect(self._pixmap_item.boundingRect())
            self.fitInView(self._pixmap_item, Qt.KeepAspectRatio)
            self._image_loaded = True

            # Set the current image filename
            if filename:
                self.current_image_filename = filename
            else:
                self.logger.warning("No filename provided when loading the image.")

            # Log successful image load
            self.logger.debug(f"Image loaded successfully in PDFGraphicsView. Pixmap item: {self._pixmap_item}")

            # Update the current page index based on the filename
            if filename and 'page_' in filename:
                try:
                    base_filename = os.path.basename(filename)
                    page_num_str = base_filename.split('_')[1].split('.')[0]
                    self.current_page_index = int(page_num_str) - 1  # Zero-based index

                    # Append to image_file_paths if the filename is not already present
                    if filename not in self.image_file_paths:
                        self.image_file_paths.append(filename)
                except (IndexError, ValueError) as e:
                    self.logger.warning(f"Unable to parse page index from filename: {filename}. Error: {e}")
            else:
                self.logger.warning(f"Filename does not follow the expected pattern: {filename}")

        except Exception as e:
            # Log any errors that occur during image loading
            self.logger.error(f"Error loading image in PDFGraphicsView: {e}", exc_info=True)
            self._image_loaded = False
            self._pixmap_item = None


    def mousePressEvent(self, event):
        try:
            if event.button() == Qt.LeftButton:
                scene_pos = self.mapToScene(event.pos())
                if self.cropping_mode:
                    # Start drawing rectangle for cropping
                    self._start_pos = scene_pos
                    self._temp_rect_item = QGraphicsRectItem()
                    self._temp_rect_item.setPen(QPen(QColor(255, 0, 0), 1, Qt.DashLine))
                    self.scene().addItem(self._temp_rect_item)
                elif self.adding_vertical_line or self.adding_horizontal_line:
                    # Start drawing line
                    self._start_pos = scene_pos
                    self._temp_line = QGraphicsLineItem()
                    self._temp_line.setPen(QPen(QColor(0, 0, 255), 1, Qt.DashLine))
                    self.scene().addItem(self._temp_line)
                elif self.manual_table_detection_mode:
                    self.modifiers = QApplication.keyboardModifiers()
                    if self.modifiers == Qt.ControlModifier:
                        # Start drawing rectangle
                        self._start_pos = scene_pos
                        self._temp_rect_item = QGraphicsRectItem()
                        self._temp_rect_item.setPen(QPen(QColor(255, 0, 0), 1, Qt.DashLine))
                        self.scene().addItem(self._temp_rect_item)
                    elif self.modifiers == Qt.ShiftModifier:
                        # Start drawing line with modifiers
                        self._start_pos = scene_pos
                        self._temp_line = QGraphicsLineItem()
                        self._temp_line.setPen(QPen(QColor(0, 0, 255), 1, Qt.DashLine))
                        self.scene().addItem(self._temp_line)
                else:
                    super().mousePressEvent(event)
            else:
                super().mousePressEvent(event)
        except Exception as e:
            self.logger.error(f"Error in mousePressEvent: {e}")
            self.show_error_message(f"An error occurred: {e}")

    def mouseMoveEvent(self, event):
        try:
            if hasattr(self, '_start_pos') and self._start_pos:
                current_pos = self.mapToScene(event.pos())
                if self.cropping_mode and hasattr(self, '_temp_rect_item') and self._temp_rect_item:
                    rect = QRectF(self._start_pos, current_pos).normalized()
                    self._temp_rect_item.setRect(rect)
                elif hasattr(self, '_temp_line') and self._temp_line:
                    if self.adding_vertical_line:
                        # Vertical line: x remains constant
                        line = QLineF(self._start_pos.x(), self._start_pos.y(), self._start_pos.x(), current_pos.y())
                    elif self.adding_horizontal_line:
                        # Horizontal line: y remains constant
                        line = QLineF(self._start_pos.x(), self._start_pos.y(), current_pos.x(), self._start_pos.y())
                    else:
                        line = QLineF(self._start_pos, current_pos)
                    self._temp_line.setLine(line)
                elif hasattr(self, '_temp_rect_item') and self._temp_rect_item:
                    rect = QRectF(self._start_pos, current_pos).normalized()
                    self._temp_rect_item.setRect(rect)
                else:
                    super().mouseMoveEvent(event)
            else:
                super().mouseMoveEvent(event)
        except Exception as e:
            self.logger.error(f"Error in mouseMoveEvent: {e}")
            self.show_error_message(f"An error occurred: {e}")

    def mouseReleaseEvent(self, event):
        try:
            if event.button() == Qt.LeftButton:
                if self.cropping_mode and hasattr(self, '_temp_rect_item') and self._temp_rect_item:
                    # Finalize rectangle and perform cropping
                    rect = self._temp_rect_item.rect()
                    self.scene().removeItem(self._temp_rect_item)
                    del self._temp_rect_item
                    self._start_pos = None

                    # Proceed to crop the image
                    self.rectangleSelected.emit(rect)

                    # Turn off cropping mode
                    self.cropping_mode = False
                    self.enable_cropping_mode(False)
                    # Uncheck the cropping action in the main window
                    main_window = self.get_main_window()
                    if main_window:
                        main_window.cropping_mode_action.setChecked(False)

                elif hasattr(self, '_temp_line') and self._temp_line:
                    # Finalize line
                    line = self._temp_line.line()
                    self.scene().removeItem(self._temp_line)
                    del self._temp_line

                    orientation = None
                    if self.adding_vertical_line:
                        orientation = 'vertical'
                    elif self.adding_horizontal_line:
                        orientation = 'horizontal'
                    elif self.manual_table_detection_mode and hasattr(self, 'modifiers') and self.modifiers == Qt.ShiftModifier:
                        delta_x = abs(line.p2().x() - line.p1().x())
                        delta_y = abs(line.p2().y() - line.p1().y())
                        orientation = 'horizontal' if delta_x > delta_y else 'vertical'

                    self.add_line(line.p1(), line.p2(), orientation)
                    # Reset flags if not in manual table detection mode
                    if not self.manual_table_detection_mode:
                        self.adding_vertical_line = False
                        self.adding_horizontal_line = False
                        # Uncheck the toolbar buttons
                        main_window = self.get_main_window()
                        if main_window:
                            main_window.add_vertical_line_action.setChecked(False)
                            main_window.add_horizontal_line_action.setChecked(False)
                elif hasattr(self, '_temp_rect_item') and self._temp_rect_item:
                    # Finalize rectangle in manual mode
                    rect = self._temp_rect_item.rect()
                    self.scene().removeItem(self._temp_rect_item)
                    del self._temp_rect_item
                    self.add_rectangle(rect)
                else:
                    super().mouseReleaseEvent(event)
                self._start_pos = None
                self.modifiers = None  # Reset modifiers
            else:
                super().mouseReleaseEvent(event)
        except Exception as e:
            self.logger.error(f"Error in mouseReleaseEvent: {e}")
            self.show_error_message(f"An error occurred: {e}")

    def wheelEvent(self, event):
        try:
            if event.modifiers() & Qt.ControlModifier:
                angle = event.angleDelta().y()
                if angle > 0:
                    self.get_main_window().zoom_in()
                elif angle < 0:
                    self.get_main_window().zoom_out()
                event.accept()
            else:
                super().wheelEvent(event)
        except Exception as e:
            self.logger.error(f"Error in wheelEvent: {e}", exc_info=True)
            super().wheelEvent(event)

    def status_bar_message(self, message, duration=5000):
        """Helper method to display messages in the status bar."""
        main_window = self.get_main_window()
        if main_window:
            main_window.status_bar.showMessage(message, duration)
        else:
            self.logger.error("Main window instance not found. Cannot display status bar message.")

    def add_rectangle_at_position(self, pos):
        """Add a rectangle at the given position."""
        try:
            scene_pos = self.mapToScene(pos)
            rect_size = QSizeF(100, 50)  # Example size, can be adjusted or made dynamic
            rect = QRectF(scene_pos, rect_size).normalized()
            rect_item = RectItem(rect)
            self.scene().addItem(rect_item)
            self._rect_items.append(rect_item)

            # Connect the moved signal
            rect_item.moved.connect(lambda new_rect, item=rect_item: self.on_rect_moved(item, new_rect))

            # Push to undo stack
            action = AddRectangleAction(self, rect_item)
            self.undo_stack.append(action)
            self.redo_stack.clear()

            self.lineModified.emit()
            self.logger.info(f"Rectangle added at {rect}")
        except Exception as e:
            self.logger.error(f"Error adding rectangle: {e}", exc_info=True)
            self.show_error_message(f"Failed to add rectangle: {e}")

    def keyPressEvent(self, event):
        try:
            if event.key() == Qt.Key_Delete:
                selected_items = self.scene().selectedItems()
                for item in selected_items:
                    if isinstance(item, QGraphicsRectItem):
                        self.remove_rectangle(item)
                    elif isinstance(item, LineItem):
                        self.remove_line(item)
            elif event.key() == Qt.Key_Z and event.modifiers() & Qt.ControlModifier:
                self.undo_last_action()
            elif event.key() == Qt.Key_Y and event.modifiers() & Qt.ControlModifier:
                self.redo_last_action()
            elif event.key() == Qt.Key_Right:
                self.get_main_window().next_page()
            elif event.key() == Qt.Key_Left:
                self.get_main_window().previous_page()
            else:
                super().keyPressEvent(event)
        except Exception as e:
            self.logger.error(f"Error in keyPressEvent: {e}")
            self.show_error_message(f"An error occurred: {e}")

    def undo_last_action(self):
        """Undo the last action."""
        try:
            if self.undo_stack:
                action = self.undo_stack.pop()
                action.undo()
                self.redo_stack.append(action)
                self.logger.info("Undo performed.")
            else:
                self.logger.info("No actions to undo.")
        except Exception as e:
            self.logger.error(f"Error performing undo: {e}", exc_info=True)
            self.show_error_message(f"Failed to undo: {e}")

    def redo_last_action(self):
        """Redo the last undone action."""
        try:
            if self.redo_stack:
                action = self.redo_stack.pop()
                action.redo()
                self.undo_stack.append(action)
                self.logger.info("Redo performed.")
            else:
                self.logger.info("No actions to redo.")
        except Exception as e:
            self.logger.error(f"Error performing redo: {e}", exc_info=True)
            self.show_error_message(f"Failed to redo: {e}")

    def get_rectangles(self):
        """Return a list of all rectangles."""
        return [item.rect() for item in self._rect_items]

    def clear_rectangles(self):
        """Clear all rectangles from the scene."""
        for item in self._rect_items:
            self.scene().removeItem(item)
        self._rect_items.clear()

    def enable_cropping_mode(self, enabled):
        """Enable or disable cropping mode."""
        self.cropping_mode = enabled
        if enabled:
            self.setDragMode(QGraphicsView.NoDrag)
        else:
            self.setDragMode(QGraphicsView.ScrollHandDrag())

    def display_lines(self, lines, key=None):
        """Display detected table lines on the image."""
        try:
            if not hasattr(self, '_pixmap_item') or self._pixmap_item is None:
                raise RuntimeError("No image loaded in PDFGraphicsView to display lines on.")

            pen = QPen(QColor(0, 255, 0), 1)  # Green lines, 1 pixel wide
            key = key or f"{self.current_page_index}_full"
            self.logger.debug(f"Displaying lines for key '{key}' with {len(lines)} lines.")

            # Clear existing lines for the key
            existing_lines = self.lines.get(key, [])
            for line_tuple in existing_lines:
                line, _ = line_tuple  # Unpack the tuple
                for item in self._line_items.copy():  # Use copy to avoid modification during iteration
                    if isinstance(item, LineItem) and item.line == line:
                        self.scene().removeItem(item)
                        self._line_items.remove(item)
                        break

            # Assign the new lines
            self.lines[key] = lines

            # Add new lines to the scene
            for line, orientation in lines:
                # Ensure that 'line' is a QLineF object and 'orientation' is a string
                if not isinstance(line, QLineF):
                    self.logger.error("Invalid line type. Expected QLineF.")
                    continue
                if orientation not in ['horizontal', 'vertical']:
                    self.logger.error(f"Invalid orientation '{orientation}'. Expected 'horizontal' or 'vertical'.")
                    continue

                # Create a LineItem with the line and its orientation
                line_item = LineItem(line, orientation=orientation)
                line_item.setPen(pen)  # Set the pen color
                self.scene().addItem(line_item)
                self._line_items.append(line_item)

                # Connect the moved signal
                line_item.moved.connect(lambda new_line, item=line_item: self.get_main_window().on_line_moved(item, new_line))

            self.logger.info(f"Displayed {len(lines)} table lines for key '{key}'.")
        except Exception as e:
            self.logger.error(f"Error displaying table lines: {e}", exc_info=True)
            self.show_error_message(f"Failed to display table lines: {e}")

    def save_lines(self):
        """
        Save all lines (automatic and manual) on the current page to the data structure.
        After saving, change their color to green.
        """
        try:
            # Retrieve the current image filename
            image_filename = self.get_current_image_filename()
            if not image_filename:
                self.logger.error("Current image filename is not set.")
                self.show_error_message("Failed to retrieve current image filename.")
                return

            # Define the key using image_filename
            key = image_filename

            # Retrieve automatic lines from self.lines[key]
            automatic_lines = self.lines.get(key, []).copy()  # Use copy to prevent modifying the original list

            # Retrieve manual lines from self._line_items
            manual_lines = [(item.line, item.orientation) for item in self._line_items]

            # Combine automatic and manual lines
            all_lines = automatic_lines + manual_lines

            # Save the combined lines back to self.lines[key]
            self.lines[key] = all_lines

            # Change the color of all lines to green
            green_pen = QPen(QColor(0, 255, 0), 1)  # Green pen, 1 pixel wide
            for item in self._line_items:
                item.setPen(green_pen)

            # Log the successful saving of lines
            self.logger.info(f"All lines on {image_filename} saved and turned green.")

            # Provide user feedback (e.g., status bar message)
            main_window = self.get_main_window()
            if main_window:
                main_window.status_bar.showMessage("Lines saved and turned green.", 5000)

            # Save the updated user lines
            self.save_user_lines(image_filename, self.lines[key])
            #self.logger.debug(f"lines[{key}]: {self.lines[key]}")

        except Exception as e:
            # Log the error with traceback
            self.logger.error(f"Error saving lines: {e}", exc_info=True)

            # Show an error message to the user
            main_window = self.get_main_window()
            if main_window:
                main_window.show_error_message(f"Failed to save lines: {e}")

    def get_lines(self):
        """Return a list of all lines with their orientations."""
        return [(item.line, item.orientation) for item in self._line_items]

    def clear_lines(self):
        """Clear all the lines from the scene."""
        for line_item in self._line_items:
            self.scene().removeItem(line_item)
        self._line_items.clear()
        # Optionally, clear from the lines dictionary
        image_filename = self.get_current_image_filename()
        if image_filename and image_filename in self.lines:
            del self.lines[image_filename]
            self.save_user_lines(image_filename, self.lines.get(image_filename, []))

class OCRApp(QMainWindow):
    ocr_completed = pyqtSignal(object)
    ocr_progress = pyqtSignal(int, int)
    ocr_error = pyqtSignal(str)
    croppedImageCreated = pyqtSignal(int, int, str)
    SUPPORTED_IMAGE_FORMATS = {'.png', '.jpg', '.jpeg'}
    SUPPORTED_PDF_FORMATS = {'.pdf'}
    logger = logging.getLogger(__name__)
    def _merge_user_lines(self, auto_TableMap, user_lines, image_list):
        """
        Merges manual lines with automatically detected lines.

        :param auto_TableMap: List of [auto_horizontal, auto_vertical] for each image.
        :param user_lines: Dictionary mapping image filenames to manual lines.
        :param image_list: List of image file paths.
        :return: List of [combined_horizontal, combined_vertical] for each image.
        """
        combined_TableMap = []
        for image_path, auto_map in zip(image_list, auto_TableMap):
            image_filename = os.path.basename(image_path)
            manual = user_lines.get(image_filename, {'horizontal': [], 'vertical': []})

            # Merge horizontal lines
            combined_horizontal = auto_map[0] + manual['horizontal']
            combined_horizontal = sorted(set(combined_horizontal))

            # Merge vertical lines
            combined_vertical = auto_map[1] + manual['vertical']
            combined_vertical = sorted(set(combined_vertical))

            combined_TableMap.append([combined_horizontal, combined_vertical])

            self.logger.debug(
                f"Merged {len(manual['horizontal'])} manual horizontal and {len(manual['vertical'])} manual vertical "
                f"lines with {len(auto_map[0])} auto horizontal and {len(auto_map[1])} auto vertical lines for image {image_filename}."
            )
        
        return combined_TableMap
    def __init__(self):
        super().__init__()

        self.setWindowTitle('PDF OCR Tool')
        self.set_app_icon()
        self.resize(1920, 1080)
        self.current_pdf_path = None
        self.rectangles = {}  # Store rectangles per page
        self.lines = {}       # Store lines per page
        self.text_size = 26  # Set default text size to 26
        self.ocr_running = False
        self.ocr_cancel_event = threading.Event()
        self.recent_files = []
        self.ocr_initialized = False
        self.init_ui()
        self.last_csv_path = None  # Store the path of the last saved CSV
        self.project_folder = None  # Store the project folder path
        self.low_confidence_cells = []  # Store low-confidence OCR results
        self.table_detection_method = 'Peaks and Troughs'  # Default method
        self.cropped_images = {}
        self.image_file_paths = []
        self.pil_images = []
        self.qimages = []
        self.setAcceptDrops(True)
        self.load_recent_files()
        self.current_page_index = 0
        self.user_lines = {}  # Store user-added lines

        # Signals for OCR processing
        self.ocr_worker = OcrGui()
        self.ocr_worker.ocr_progress.connect(self.update_progress_bar)
        self.ocr_worker.ocr_progress.connect(self.update_remaining_time_label)
        self.ocr_worker.ocr_completed.connect(self.on_ocr_completed)
        self.ocr_worker.ocr_error.connect(self.show_error_message)
        self.graphics_view.rectangleSelected.connect(self.on_rectangle_selected)
        self.graphics_view.lineModified.connect(self.on_line_modified)
    
    def init_ui(self):
        splitter = QSplitter(Qt.Horizontal)
        self.graphics_view = PDFGraphicsView(self)
        splitter.addWidget(self.graphics_view)

        # Initialize project_list as QTreeWidget
        self.project_list = QTreeWidget()
        self.project_list.setHeaderLabel("Project Pages")
        splitter.addWidget(self.project_list)
        self.project_list.currentItemChanged.connect(self.change_page)

        splitter.setSizes([1900, 400])

        self.setCentralWidget(splitter)

        self.init_menu_bar()
        self.init_output_dock()
        self.init_tool_bar()
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.progress_bar = None

        sys.stdout = EmittingStream(textWritten=self.normal_output_written)
        sys.stderr = EmittingStream(textWritten=self.error_output_written)

        self.setStyleSheet(f"font-size: {self.text_size}px;")

        self.ocr_completed.connect(self.on_ocr_completed)
        self.ocr_progress.connect(self.on_ocr_progress)
        self.ocr_error.connect(self.on_ocr_error)

        self.graphics_view.lineModified.connect(self.on_line_modified)

        # Connect the croppedImageCreated signal
        self.croppedImageCreated.connect(self.graphics_view.get_main_window().update_project_list)
    
    def init_menu_bar(self):
        menu_bar = self.menuBar()
        # File Menu
        file_menu = menu_bar.addMenu('File')

        open_action = QAction('Open', self)
        open_action.setShortcut('Ctrl+O')
        open_action.triggered.connect(self.open_pdf)
        file_menu.addAction(open_action)

        self.recent_files_menu = file_menu.addMenu('Recent Files')
        self.update_recent_files_menu()

        save_project_action = QAction('Save Project', self)
        save_project_action.triggered.connect(self.save_project)
        file_menu.addAction(save_project_action)

        load_project_action = QAction('Load Project', self)
        load_project_action.triggered.connect(self.load_project)
        file_menu.addAction(load_project_action)

        save_as_action = QAction('Save As', self)
        save_as_action.setShortcut('Ctrl+S')
        save_as_action.triggered.connect(self.save_as)
        file_menu.addAction(save_as_action)

        exit_action = QAction('Exit', self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Edit Menu (this is where undo and redo should be placed)
        edit_menu = menu_bar.addMenu('Edit')

        # Undo Action
        self.undo_action = QAction('Undo', self)
        self.undo_action.setShortcut('Ctrl+Z')
        self.undo_action.triggered.connect(self.graphics_view.undo_last_action)
        edit_menu.addAction(self.undo_action)

        # Redo Action
        self.redo_action = QAction('Redo', self)
        self.redo_action.setShortcut('Ctrl+Y')
        self.redo_action.triggered.connect(self.graphics_view.redo_last_action)
        edit_menu.addAction(self.redo_action)

        # View Menu
        view_menu = menu_bar.addMenu('View')

        # Zoom In
        self.zoom_in_action = QAction('Zoom In', self)
        self.zoom_in_action.setShortcut('Ctrl++')
        self.zoom_in_action.triggered.connect(self.zoom_in)
        self.zoom_in_action.setEnabled(False)
        view_menu.addAction(self.zoom_in_action)

        # Zoom Out
        self.zoom_out_action = QAction('Zoom Out', self)
        self.zoom_out_action.setShortcut('Ctrl+-')
        self.zoom_out_action.triggered.connect(self.zoom_out)
        self.zoom_out_action.setEnabled(False)
        view_menu.addAction(self.zoom_out_action)

        # Reset Zoom
        self.reset_zoom_action = QAction('Reset Zoom', self)
        self.reset_zoom_action.triggered.connect(self.reset_zoom)
        self.reset_zoom_action.setEnabled(False)
        view_menu.addAction(self.reset_zoom_action)

        # Fit to Screen
        self.fit_to_screen_action = QAction('Fit to Screen', self)
        self.fit_to_screen_action.triggered.connect(self.fit_to_screen)
        self.fit_to_screen_action.setEnabled(False)
        view_menu.addAction(self.fit_to_screen_action)

        # Navigation: Previous Page and Next Page
        prev_action = QAction('Previous Page', self)
        prev_action.setShortcut('Ctrl+Left')
        prev_action.triggered.connect(self.previous_page)
        view_menu.addAction(prev_action)

        next_action = QAction('Next Page', self)
        next_action.setShortcut('Ctrl+Right')
        next_action.triggered.connect(self.next_page)
        view_menu.addAction(next_action)

        # Text Size Submenu
        text_size_menu = view_menu.addMenu('Text Size')
        sizes = ['18', '20', '22', '24', '26', '28', '30', '32', '34', '36']
        for size in sizes:
            size_action = QAction(size, self)
            size_action.triggered.connect(lambda checked, s=size: self.change_text_size(s))
            text_size_menu.addAction(size_action)

        # Table Detection Method Menu
        method_menu = menu_bar.addMenu('Table Detection Method')

        peaks_troughs_action = QAction('Peaks and Troughs', self)
        peaks_troughs_action.setCheckable(True)
        peaks_troughs_action.setChecked(True)
        peaks_troughs_action.triggered.connect(lambda: self.set_table_detection_method('Peaks and Troughs'))
        method_menu.addAction(peaks_troughs_action)

        transitions_action = QAction('Transitions', self)
        transitions_action.setCheckable(True)
        transitions_action.setChecked(False)
        transitions_action.triggered.connect(lambda: self.set_table_detection_method('Transitions'))
        method_menu.addAction(transitions_action)

        # Create an action group to make actions exclusive
        method_group = QActionGroup(self)
        method_group.addAction(peaks_troughs_action)
        method_group.addAction(transitions_action)
        method_group.setExclusive(True)

        # Help Menu
        help_menu = menu_bar.addMenu('Help')

        how_to_use_action = QAction('How to Use', self)
        how_to_use_action.triggered.connect(self.show_help_tab_from_file)
        help_menu.addAction(how_to_use_action)

        terms_action = QAction('Terms of Service', self)
        terms_action.triggered.connect(lambda: self.show_help_tab('Terms of Service', 'Terms of Service text goes here.'))
        help_menu.addAction(terms_action)

        license_action = QAction('License', self)
        license_action.triggered.connect(lambda: self.show_help_tab('License', 'License text goes here.'))
        help_menu.addAction(license_action)

    def init_tool_bar(self):
        tool_bar = QToolBar("Main Toolbar")
        self.addToolBar(Qt.TopToolBarArea, tool_bar)

        # New action for OCR on selected pages
        self.run_ocr_selected_pages_action = QAction('Page Select', self)
        self.run_ocr_selected_pages_action.triggered.connect(self.run_ocr_on_selected_pages)
        tool_bar.addAction(self.run_ocr_selected_pages_action)

        # Run OCR - Initially Hidden
        self.run_ocr_action = QAction('Run OCR', self)
        self.run_ocr_action.triggered.connect(self.run_ocr)
        self.run_ocr_action.setVisible(False)  # Hide the button initially
        tool_bar.addAction(self.run_ocr_action)

        # Detect Tables Action
        self.detect_tables_action = QAction('Detect Tables', self)
        self.detect_tables_action.triggered.connect(self.detect_tables)
        self.detect_tables_action.setEnabled(True)
        tool_bar.addAction(self.detect_tables_action)

        # Cropping Mode Toggle
        self.cropping_mode_action = QAction('Cropping Mode', self)
        self.cropping_mode_action.setCheckable(True)
        self.cropping_mode_action.setChecked(False)
        self.cropping_mode_action.setEnabled(False)
        self.cropping_mode_action.triggered.connect(self.toggle_cropping_mode)
        tool_bar.addAction(self.cropping_mode_action)

        # Zoom In
        self.zoom_in_action = QAction('+', self)
        self.zoom_in_action.setShortcut('Ctrl++')
        self.zoom_in_action.triggered.connect(self.zoom_in)
        self.zoom_in_action.setEnabled(False)
        tool_bar.addAction(self.zoom_in_action)

        # Zoom Out
        self.zoom_out_action = QAction('-', self)
        self.zoom_out_action.setShortcut('Ctrl+-')
        self.zoom_out_action.triggered.connect(self.zoom_out)
        self.zoom_out_action.setEnabled(False)
        tool_bar.addAction(self.zoom_out_action)

        # Toggle Editing Mode
        self.edit_mode_action = QAction('Editing Mode', self)
        self.edit_mode_action.setCheckable(True)
        self.edit_mode_action.setChecked(True)
        self.edit_mode_action.setEnabled(True)
        self.edit_mode_action.triggered.connect(self.toggle_edit_mode)
        tool_bar.addAction(self.edit_mode_action)

        # Manual Table Detection Action
        self.manual_table_detection_action = QAction("Manual Table Detection", self)
        self.manual_table_detection_action.setCheckable(True)
        self.manual_table_detection_action.triggered.connect(self.graphics_view.enable_manual_table_detection)
        tool_bar.addAction(self.manual_table_detection_action)

        # Add Vertical Line Action
        self.add_vertical_line_action = QAction('Line |', self)
        self.add_vertical_line_action.setCheckable(True)
        self.add_vertical_line_action.triggered.connect(lambda checked: self.graphics_view.toggle_add_vertical_line_mode(checked))
        tool_bar.addAction(self.add_vertical_line_action)

        # Add Horizontal Line Action
        self.add_horizontal_line_action = QAction('Line --', self)
        self.add_horizontal_line_action.setCheckable(True)
        self.add_horizontal_line_action.triggered.connect(lambda checked: self.graphics_view.toggle_add_horizontal_line_mode(checked))
        tool_bar.addAction(self.add_horizontal_line_action)

        # Group the line actions to make them exclusive
        self.line_action_group = QActionGroup(self)
        self.line_action_group.addAction(self.add_vertical_line_action)
        self.line_action_group.addAction(self.add_horizontal_line_action)
        self.line_action_group.setExclusive(True)

        self.save_lines_action = QAction('Save Lines', self)
        self.save_lines_action.triggered.connect(self.save_lines)
        self.save_lines_action.setEnabled(False)  # Initially disabled
        tool_bar.addAction(self.save_lines_action)
        # Separator
        tool_bar.addSeparator()

        # Save CSV Action
        self.save_csv_action = QAction('Save CSV', self)
        self.save_csv_action.triggered.connect(self.save_csv)
        self.save_csv_action.setEnabled(False)
        tool_bar.addAction(self.save_csv_action)

        # Export to Excel
        self.export_excel_action = QAction('Export to Excel', self)
        self.export_excel_action.triggered.connect(self.export_to_excel)
        self.export_excel_action.setEnabled(False)  # Initially disabled
        tool_bar.addAction(self.export_excel_action)
        
        # Add 'Show Output' button using the dock's toggleViewAction
        show_output_action = self.output_dock.toggleViewAction()
        show_output_action.setText('Show dock')
        tool_bar.addAction(show_output_action)

    def init_output_dock(self):

        # Create the Output Dock
        self.output_dock = QDockWidget('Output', self)
        self.output_dock.setAllowedAreas(Qt.BottomDockWidgetArea | Qt.TopDockWidgetArea)

        # Create a central widget for the dock and set a vertical layout
        dock_widget = QWidget()
        dock_layout = QVBoxLayout()
        dock_widget.setLayout(dock_layout)

        # Create a tab widget to hold the outputs
        self.output_tabs = QTabWidget()
        dock_layout.addWidget(self.output_tabs)

        # Add tabs to the tab widget
        # 1. Log Output Tab
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.output_tabs.addTab(self.log_output, 'Log Output')

        # 2. Table View Tab
        self.tableWidget = QTableWidget()
        self.output_tabs.addTab(self.tableWidget, 'Table View')

        # 3. CSV Output Preview Tab
        self.csv_output = QTextEdit()
        self.csv_output.setReadOnly(True)
        self.output_tabs.addTab(self.csv_output, 'CSV Output')

        # Initialize Remaining Time Label
        self.remaining_time_label = QLabel("Estimated remaining time: N/A", self)
        self.remaining_time_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.remaining_time_label.setStyleSheet("font-size: 26px;")  # Optional: Adjust font size

        # Add the remaining_time_label to the dock layout
        dock_layout.addWidget(self.remaining_time_label)

        # Set the dock's central widget
        self.output_dock.setWidget(dock_widget)

        # Add the dock to the main window at the bottom
        self.addDockWidget(Qt.BottomDockWidgetArea, self.output_dock)

        # Optionally, raise the dock to ensure it's visible
        self.output_dock.raise_()
        
    def set_app_icon(self):
        """Set the application window icon using a relative path."""
        # Get the absolute path to the directory containing this script
        script_dir = os.path.dirname(os.path.abspath(__file__))

        # Construct the full path to the icon.png
        icon_path = os.path.join(script_dir, 'icon_1_Improved.png')

        # Check if the icon file exists
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
            self.logger.info(f"Window icon set to {icon_path}")
        else:
            self.logger.warning(f"Icon file not found at {icon_path}")

    def update_lines(self, image_filename, lines):
        """Slot to update self.lines with lines from PDFGraphicsView."""
        self.lines[image_filename] = lines
        self.logger.debug(f"Updated lines for {image_filename}: {lines}")

    def show_help_tab(self, title, content):
        try:
            # Create a QWidget to hold the QTextBrowser
            help_widget = QWidget()
            layout = QVBoxLayout()
            help_widget.setLayout(layout)

            # Create a QTextBrowser to display the text content
            text_browser = QTextBrowser()
            text_browser.setPlainText(content)  # Use setPlainText for plain text
            text_browser.setReadOnly(True)
            text_browser.setOpenExternalLinks(True)  # Enable clickable links if any

            layout.addWidget(text_browser)

            # Check if the tab already exists
            for index in range(self.output_tabs.count()):
                if self.output_tabs.tabText(index) == title:
                    self.output_tabs.setCurrentIndex(index)
                    return

            # Add the help_widget as a new tab
            self.output_tabs.addTab(help_widget, title)
            self.output_tabs.setCurrentWidget(help_widget)

            self.logger.info(f"Help tab '{title}' displayed successfully.")
        except Exception as e:
            self.logger.error(f"Error displaying help tab: {e}", exc_info=True)
            QMessageBox.critical(self, "Error", f"An error occurred while displaying help:\n{e}")

    def show_help_tab_from_file(self):
        try:
            help_file_path = os.path.join(os.path.dirname(__file__), 'help.txt')
            if not os.path.exists(help_file_path):
                self.logger.error(f"Help file not found at {help_file_path}")
                QMessageBox.warning(self, "Help File Missing", f"The help file 'help.txt' was not found in the application directory.")
                return

            with open(help_file_path, 'r', encoding='utf-8') as file:
                help_content = file.read()

            # Display the help content in a new tab
            self.show_help_tab("How to Use", help_content)

        except Exception as e:
            self.logger.error(f"Failed to load help file: {e}", exc_info=True)
            QMessageBox.critical(self, "Error", f"An error occurred while loading the help file:\n{e}")

    def update_progress_bar(self, tasks_completed, total_tasks):
        progress_percentage = int((tasks_completed / total_tasks) * 100)
        self.progress_bar.setValue(progress_percentage)

    def update_remaining_time_label(self, remaining_time):
        # Format the remaining_time into minutes and seconds
        minutes, seconds = divmod(int(remaining_time), 60)
        time_str = f"Estimated remaining time: {minutes}m {seconds}s"
        self.remaining_time_label.setText(time_str)
        #self.logger.debug(f"Updated remaining_time_label: {time_str}")

    def set_table_detection_method(self, method_name):
        self.table_detection_method = method_name
        self.status_bar.showMessage(f'Table Detection Method set to: {method_name}', 5000)

    def update_recent_files_menu(self):
        self.recent_files_menu.clear()
        for file_path in self.recent_files:
            file_name = os.path.basename(file_path)
            action = QAction(file_name, self)
            action.setData(file_path)
            action.triggered.connect(lambda checked, path=file_path: self.open_recent_file(path))
            self.recent_files_menu.addAction(action)

    def load_recent_files(self):
        """Load recent files from an external JSON log file."""
        try:
            recent_files_path = os.path.join(self.project_folder or os.getcwd(), 'recent_files.json')
            if os.path.exists(recent_files_path):
                with open(recent_files_path, 'r', encoding='utf-8') as f:
                    self.recent_files = json.load(f)
                self.logger.info("Recent files loaded successfully.")
            else:
                self.recent_files = []
        except Exception as e:
            self.logger.error(f"Failed to load recent files: {e}", exc_info=True)
            self.recent_files = []

    def save_recent_files(self):
        """Save recent files to an external JSON log file."""
        try:
            recent_files_path = os.path.join(self.project_folder or os.getcwd(), 'recent_files.json')
            with open(recent_files_path, 'w', encoding='utf-8') as f:
                json.dump(self.recent_files, f, indent=4)
            self.logger.info("Recent files saved successfully.")
        except Exception as e:
            self.logger.error(f"Failed to save recent files: {e}", exc_info=True)

    def update_recent_files(self, file_path):
        """Add a file to the recent files list without duplicates."""
        if file_path in self.recent_files:
            self.recent_files.remove(file_path)
        self.recent_files.insert(0, file_path)
        if len(self.recent_files) > 5:
            self.recent_files = self.recent_files[:5]
        self.update_recent_files_menu()

    def open_recent_file(self, file_path):
        """Open a file from the recent files list."""
        if os.path.exists(file_path):
            self.process_files([file_path])
            self.update_recent_files(file_path)
        else:
            QMessageBox.warning(self, 'File Not Found', f'The file {file_path} does not exist.')
            self.recent_files.remove(file_path)
            self.update_recent_files_menu()

    def detect_tables(self):
        """Detect tables in the currently selected page or cropped image."""
        try:
            current_item = self.project_list.currentItem()
            if not current_item:
                self.show_error_message("No item selected for table detection.")
                return

            selected_text = current_item.text(0)

            # Get the image path from the item data
            image_path = current_item.data(0, Qt.UserRole)
            if not image_path or not os.path.exists(image_path):
                self.show_error_message("Image file not found for the selected item.")
                return

            # Determine if the selected item is a Page or Cropped image
            if selected_text.startswith("Page"):
                page_index = int(selected_text.split(" ")[1]) - 1
                self.perform_table_detection(image_path, page_index=page_index, is_pdf=False, cropped_index=None)

            elif selected_text.startswith("Cropped"):
                # Handle cropped images (similar logic can be applied)
                pass  # Implement as needed

            else:
                self.show_error_message("Invalid selection for table detection.")
                return

        except Exception as e:
            self.logger.error(f"Error in detect_tables: {e}", exc_info=True)
            self.show_error_message(f"An error occurred during table detection: {e}")

    def perform_table_detection(self, image_path, page_index, is_pdf=True, cropped_index=None):
        """Helper method to perform table detection on a single image."""
        try:
            # Detect tables using ocr_module's detect_tables_in_images method
            table_map = ocr_module.detect_tables_in_images([image_path])  # Pass a list with a single image

            if not table_map or not table_map[0]:
                self.show_error_message(f"No tables detected in {'cropped image' if cropped_index is not None else 'page/image'} {page_index + 1}")
                self.logger.warning(f"No tables detected in {'cropped image' if cropped_index is not None else 'page/image'} {page_index + 1}")
                return

            # Assume horizontal_positions and vertical_positions might be pairs of values (min, max)
            horizontal_positions, vertical_positions = table_map[0]  # Unpack detected table coordinates

            # Convert positions to QLineF objects for drawing lines
            lines = []
            pil_image = Image.open(image_path)
            image_width, image_height = pil_image.size

            # Draw horizontal lines
            for y in horizontal_positions:
                if isinstance(y, list) and len(y) == 2:  # If it's a list (min, max), use the first value for the line
                    y_min, y_max = y
                    line = QLineF(0.0, float(y_min), float(image_width), float(y_min))
                else:
                    line = QLineF(0.0, float(y), float(image_width), float(y))
                lines.append((line, 'horizontal'))  # Append tuple with orientation

            # Draw vertical lines
            for x in vertical_positions:
                if isinstance(x, list) and len(x) == 2:  # If it's a list (min, max), use the first value for the line
                    x_min, x_max = x
                    line = QLineF(float(x_min), 0.0, float(x_min), float(image_height))
                else:
                    line = QLineF(float(x), 0.0, float(x), float(image_height))
                lines.append((line, 'vertical'))  # Append tuple with orientation

            # Store lines with the correct key (depending on cropped or full image)
            if cropped_index is not None:
                key = f"{page_index}_{cropped_index}"
            else:
                key = f"{page_index}_full"
            self.lines[key] = lines  # Assign list of tuples

            # Ensure the correct image is displayed in the graphics view
            if self.current_page_index != page_index:
                self.current_page_index = page_index
                self.show_current_page()

            # Load the image into the graphics view (if not already loaded)
            if not self.graphics_view._image_loaded:
                # Convert PIL image to QImage
                pil_image = self.pil_images[page_index]
                qimage = pil_image.convert("RGBA").toqimage()
                self.graphics_view.load_image(qimage, filename=image_path)

            # Display the detected lines in the graphics view
            self.graphics_view.display_lines(lines, key=key)

            self.logger.info(f"Table detection completed for {'cropped image' if cropped_index is not None else 'page/image'} {page_index + 1}")

        except Exception as e:
            # Handle exceptions and show error messages
            if cropped_index is not None:
                self.show_error_message(f"Table detection on cropped image failed: {e}")
                self.logger.error(f"Table detection on cropped image {cropped_index + 1} of page {page_index + 1} failed: {e}", exc_info=True)
            else:
                self.show_error_message(f"Table detection on {'page' if is_pdf else 'image'} failed: {e}")
                self.logger.error(f"Table detection on {'page' if is_pdf else 'image'} {page_index + 1} failed: {e}", exc_info=True)

    def open_pdf(self):
        options = QFileDialog.Options()
        file_name, _ = QFileDialog.getOpenFileName(
            self, 
            "Open PDF", 
            "", 
            "PDF Files (*.pdf);;All Files (*)", 
            options=options
        )
        if file_name:
            self.load_pdf_file(file_name)
        else:
            self.logger.warning("No file selected.")

    def load_pdf_file(self, file_name):
        try:
            self.current_pdf_path = file_name
            self.logger.info(f"PDF file selected: {file_name}")

            # Set the project folder based on the PDF name
            pdf_name = os.path.splitext(os.path.basename(file_name))[0]
            project_folder = os.path.join(os.getcwd(), pdf_name)
            os.makedirs(project_folder, exist_ok=True)

            # Assign project_folder to self.project_folder
            self.project_folder = project_folder

            # Process the PDF into images and save them in temp_images directory
            self.process_pdf_to_images(file_name, project_folder)

            # Update recent files list
            self.update_recent_files(file_name)

            # Add the new project to the project explorer
            self.add_project_to_explorer(pdf_name, project_folder)

            # Select the first page of the new project
            self.select_first_page(pdf_name)

        except Exception as e:
            self.logger.error(f"Failed to load PDF: {e}", exc_info=True)
            self.show_error_message(f"Failed to load PDF: {e}")

    def dragEnterEvent(self, event: QDragEnterEvent):
        self.logger.debug("MainWindow: Drag Enter Event detected.")
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                if url.isLocalFile():
                    file_path = url.toLocalFile()
                    _, ext = os.path.splitext(file_path)
                    self.logger.debug(f"MainWindow: Dragged file: {file_path}, Extension: {ext}")
                    if ext.lower() in self.SUPPORTED_PDF_FORMATS.union(self.SUPPORTED_IMAGE_FORMATS):
                        self.logger.debug("MainWindow: File format supported. Accepting drag event.")
                        event.acceptProposedAction()
                        return
        self.logger.debug("MainWindow: File format not supported or no URLs. Ignoring drag event.")
        event.ignore()

    def dropEvent(self, event: QDropEvent):
        self.logger.debug("MainWindow: Drop Event detected.")
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                if url.isLocalFile():
                    file_path = url.toLocalFile()
                    self.logger.debug(f"MainWindow: Dropped file: {file_path}")
                    _, ext = os.path.splitext(file_path)
                    ext = ext.lower()
                    self.logger.debug(f"MainWindow: File extension: {ext}")
                    if ext in self.SUPPORTED_PDF_FORMATS or ext in self.SUPPORTED_IMAGE_FORMATS:
                        self.logger.debug("MainWindow: File is a PDF or supported image. Processing.")
                        self.process_files([file_path])
                        self.update_recent_files(file_path)
                        event.acceptProposedAction()
                    else:
                        self.logger.warning("MainWindow: Invalid file type dropped.")
                        self.show_error_message("Invalid file type. Only PDF or image files supported.")
                        event.ignore()
        else:
            self.logger.debug("MainWindow: No URLs in drop event.")
            event.ignore()

    def process_pdf_to_images(self, pdf_path, project_folder):
        """Processes the PDF into images and saves them in the project folder using PyMuPDF."""
        try:
            image_dir = os.path.join(project_folder, 'temp_images')
            os.makedirs(image_dir, exist_ok=True)

            # Use PyMuPDF to convert PDF pages to images
            from pdf_to_image import pdf_to_images  # Ensure this import matches your project structure
            images = pdf_to_images(pdf_path, dpi=400)
            self.image_file_paths = []
            self.pil_images = []  # Initialize the list to store PIL images

            for i, page_image in enumerate(images):
                image_path = os.path.join(image_dir, f'page_{i + 1}.png')
                page_image.save(image_path, 'PNG')
                self.image_file_paths.append(image_path)
                self.pil_images.append(page_image)  # Add the PIL image to the list
                self.logger.debug(f"Added PIL image for page {i+1}")

            self.logger.debug(f"Total images processed: {len(self.pil_images)}")
            self.logger.info(f"PDF processed into images at: {image_dir}")

        except Exception as e:
            self.logger.error(f"Error processing PDF to images: {e}", exc_info=True)
            self.show_error_message(f"Failed to process PDF into images: {e}")


    def select_first_page(self, pdf_name):
        try:
            # Find the project item
            project_item = None
            for i in range(self.project_list.topLevelItemCount()):
                item = self.project_list.topLevelItem(i)
                if item.text(0) == pdf_name:
                    project_item = item
                    break

            if not project_item:
                self.logger.warning(f"Project '{pdf_name}' not found in project list.")
                return

            # Select the first page
            if project_item.childCount() > 0:
                first_page_item = project_item.child(0)
                self.project_list.setCurrentItem(first_page_item)
                self.logger.info(f"Automatically selected the first page: {first_page_item.text(0)}")
            else:
                self.logger.warning(f"No pages found under project '{pdf_name}'.")
        except Exception as e:
            self.logger.error(f"Error selecting first page: {e}", exc_info=True)
            self.show_error_message(f"Failed to select first page: {e}")

    def find_project_item(self, project_name):
        """Finds and returns the QTreeWidgetItem for the given project name."""
        for i in range(self.project_list.topLevelItemCount()):
            item = self.project_list.topLevelItem(i)
            if item.text(0) == project_name:
                return item
        return None

    def next_page(self):
        """Navigate to the next page of the PDF."""
        try:
            if self.pdf_images and self.current_page_index + 1 < len(self.pdf_images):
                self.current_page_index += 1
                self.load_image(self.pdf_images[self.current_page_index])
                self.get_main_window().update_page_label(self.current_page_index)
            else:
                self.logger.warning("No next page available.")
        except Exception as e:
            self.logger.error(f"Error in next_page: {e}")
            self.get_main_window().show_error_message(f"An error occurred: {e}")

    def previous_page(self):
        """Navigate to the previous page of the PDF."""
        try:
            if self.pdf_images and self.current_page_index - 1 >= 0:
                self.current_page_index -= 1
                self.load_image(self.pdf_images[self.current_page_index])
                self.get_main_window().update_page_label(self.current_page_index)
            else:
                self.logger.warning("No previous page available.")
        except Exception as e:
            self.logger.error(f"Error in previous_page: {e}")
            self.get_main_window().show_error_message(f"An error occurred: {e}")
   
    def on_rectangle_selected(self, rect):
        """Handle the event when a rectangle is selected for cropping in the graphics view."""
        try:
            self.logger.info(f"Cropping area selected on page {self.current_page_index + 1}: {rect}")

            # Get the current PIL image
            pil_image = self.pil_images[self.current_page_index]
            if pil_image is None:
                raise ValueError("No PIL image found for current page.")

            # Crop the selected area using the PIL image
            cropped_image = self.crop_image_pil(pil_image, rect)
            if cropped_image is None:
                raise ValueError("Cropping returned None.")

            # Save the cropped image
            cropped_image_path, page_index, cropped_index = self.save_cropped_image(cropped_image, rect)

            if cropped_image_path:
                # Update the project list to show the new cropped image
                self.update_project_list(self.current_pdf_path, page_index, cropped_index, cropped_image_path)

                # Turn off cropping mode
                self.cropping_mode_action.setChecked(False)
                self.graphics_view.enable_cropping_mode(False)
                self.logger.info("Cropping mode turned off after cropping action.")
            else:
                self.logger.error("Failed to save cropped image.")

        except IndexError as e:
            self.logger.error(f"Index error in on_rectangle_selected: {e}")
            self.show_error_message(f"An error occurred: {e}")

        except Exception as e:
            self.logger.error(f"Error cropping image: {e}", exc_info=True)
            self.show_error_message(f"Failed to crop image: {e}")

    def detect_line_intersections(self):
        """Detect intersections between vertical and horizontal lines and record them as table bounding boxes."""
        try:
            vertical_lines = [line for line in self.graphics_view._line_items if line.orientation == 'vertical']
            horizontal_lines = [line for line in self.graphics_view._line_items if line.orientation == 'horizontal']
            bounding_boxes = []

            for v_line in vertical_lines:
                v_x = v_line.line.p1().x()
                for h_line in horizontal_lines:
                    h_y = h_line.line.p1().y()
                    bounding_boxes.append(QRectF(v_x, h_y, 1, 1))  # Tiny rectangles at intersections

            self.bounding_boxes = bounding_boxes
            self.logger.info(f"Detected {len(bounding_boxes)} intersections.")
            self.status_bar.showMessage(f"Detected {len(bounding_boxes)} table intersections.", 5000)
        except Exception as e:
            self.logger.error(f"Error detecting intersections: {e}", exc_info=True)
            self.show_error_message(f"Failed to detect table intersections: {e}")

    def determine_orientation(self, line_tuple):
        try:
            if isinstance(line_tuple, tuple) and len(line_tuple) == 2:
                line, orientation = line_tuple
                if orientation in ['horizontal', 'vertical']:
                    return orientation
                else:
                    # Fallback to calculating orientation if invalid
                    angle = line.angle()
                    return 'horizontal' if angle < 45 or angle > 135 else 'vertical'
            elif isinstance(line_tuple, QLineF):
                angle = line_tuple.angle()
                return 'horizontal' if angle < 45 or angle > 135 else 'vertical'
            else:
                self.logger.error("Invalid input for determine_orientation.")
                return 'unknown'
        except Exception as e:
            self.logger.error(f"Error determining orientation: {e}", exc_info=True)
            return 'unknown'

    def preview_cropped_image(self, cropped_image):
        """Preview the cropped image in a separate window or UI element."""
        qimage = self.pil_image_to_qimage(cropped_image)
        preview_window = QLabel(self)
        pixmap = QPixmap.fromImage(qimage)
        preview_window.setPixmap(pixmap)
        preview_window.setWindowTitle("Cropped Image Preview")
        preview_window.resize(pixmap.width(), pixmap.height())
        preview_window.show()

    def on_line_modified(self):
        """Handle the event when a line is modified in PDFGraphicsView."""
        self.logger.info(f"Line modified on page {self.graphics_view.current_page_index + 1}")
        
        # Save lines from PDFGraphicsView
        self.save_lines()
        
        # Detect intersections or perform other necessary actions
        self.detect_line_intersections()
        
        # Update OCRApp's lines dictionary from PDFGraphicsView
        image_filename = self.graphics_view.get_current_image_filename()
        if image_filename:
            lines = self.graphics_view.get_lines_for_image(image_filename)
            self.lines[image_filename] = lines
            #self.logger.debug(f"Updated lines for {image_filename}: {lines}")

    def get_user_lines_for_pages(self, selected_pages):
        """
        Retrieves user-defined lines for the selected pages from the GUI.
        Converts QLineF objects to numerical positions.

        :param selected_pages: List of zero-based page indices.
        :return: Dictionary mapping image filenames to their respective manual lines.
        """
        user_lines = {}
        for page_index in selected_pages:
            if 0 <= page_index < len(self.image_file_paths):
                image_filename = os.path.basename(self.image_file_paths[page_index])
                lines = self.graphics_view.get_lines_for_image(image_filename)  # Returns list of (QLineF, orientation)
                
                manual_horizontal = []
                manual_vertical = []
                
                for line, orientation in lines:
                    if orientation == 'horizontal':
                        # Extract y-coordinate (average of y1 and y2)
                        y = (line.y1() + line.y2()) / 2
                        y = round(y, 2)  # Optional: Round for precision
                        manual_horizontal.append(y)
                        self.logger.debug(f"User added horizontal line: y={y}")
                    elif orientation == 'vertical':
                        # Extract x-coordinate (average of x1 and x2)
                        x = (line.x1() + line.x2()) / 2
                        x = round(x, 2)  # Optional: Round for precision
                        manual_vertical.append(x)
                        self.logger.debug(f"User added vertical line: x={x}")
                    else:
                        self.logger.warning(f"Unknown orientation: {orientation}")
                
                user_lines[image_filename] = {
                    'horizontal': manual_horizontal,
                    'vertical': manual_vertical
                }
                self.logger.debug(f"User lines for {image_filename}: {user_lines[image_filename]}")
        return user_lines


    def change_page(self, current_item, previous_item):
        """Handle page changes when a different page is selected from the project list."""
        try:
            if not current_item:
                return

            selected_text = current_item.text(0)
            self.logger.debug(f"Selected item: {selected_text}")

            if selected_text.startswith("Page"):
                # Selected a full page
                page_index = int(selected_text.split(" ")[1]) - 1
                self.current_page_index = page_index
                self.show_current_page()

            elif selected_text.startswith("Cropped"):
                # Selected a cropped image
                parent_item = current_item.parent()
                if not parent_item:
                    self.logger.warning("Cropped item without a parent. Ignoring selection.")
                    return

                parent_text = parent_item.text(0)
                page_index = int(parent_text.split(" ")[1]) - 1

                # Extract the cropped index from the text
                cropped_text = selected_text.split(":")[0]  # e.g., "Cropped 1"
                cropped_index = int(cropped_text.split(" ")[1]) - 1

                self.show_cropped_image(page_index, cropped_index)

        except Exception as e:
            self.logger.error(f"Error changing page: {e}", exc_info=True)
            self.show_error_message(f"An error occurred while changing page: {e}")

    def show_cropped_image(self, page_index, cropped_index):
        """Display the cropped image in the graphics view."""
        try:
            cropped_image_path = self.cropped_images[page_index][cropped_index]
            
            # Check if the file exists
            if not os.path.exists(cropped_image_path):
                self.logger.error(f"Cropped image file does not exist: {cropped_image_path}")
                self.show_error_message(f"Cropped image file does not exist: {cropped_image_path}")
                return

            # Open the cropped image as a PIL Image
            try:
                cropped_image = Image.open(cropped_image_path)
                cropped_image = cropped_image.convert('RGB')  # Ensure it's in RGB mode
            except (IOError, SyntaxError) as e:
                self.logger.error(f"Invalid image file: {cropped_image_path} - {e}")
                self.show_error_message(f"Invalid image file: {cropped_image_path} - {e}")
                return

            # Convert to QImage
            qimage = self.pil_image_to_qimage(cropped_image)
            
            # Add the cropped image to pil_images and qimages for potential future operations
            self.pil_images.append(cropped_image)
            self.qimages.append(qimage)
            
            # Update current page index to the cropped image
            self.current_page_index = len(self.pil_images) - 1
            
            # Load the image into the graphics view
            self.graphics_view.load_image(qimage, filename=cropped_image_path)

            # Log the successful loading of the cropped image
            self.logger.info(f'Successfully displayed cropped image from page {page_index + 1}, cropped index {cropped_index + 1}')

            # Clear existing rectangles and lines as this is a cropped image
            self.graphics_view.clear_rectangles()
            self.graphics_view.clear_lines()

        except Exception as e:
            self.logger.error(f"Failed to display cropped image {cropped_index + 1} from page {page_index + 1}: {e}", exc_info=True)
            self.show_error_message(f"An error occurred while displaying cropped image: {e}")

    def load_image(self, file_path):
        """Load a single image file and add it to the project."""
        try:
            # Open the image using PIL
            pil_image = Image.open(file_path).convert('RGB')  # Ensure consistency in image mode
            self.pil_images.append(pil_image)

            # Convert PIL Image to QImage
            qimage = self.pil_image_to_qimage(pil_image)
            self.qimages.append(qimage)

            # Save the image as a PNG file in the temporary directory
            temp_dir = Path('temp_images')
            temp_dir.mkdir(exist_ok=True)
            page_index = len(self.pil_images) - 1  # Zero-based index
            image_file_path = temp_dir / f"image_{page_index + 1}.png"
            pil_image.save(image_file_path, "PNG")
            self.image_file_paths.append(str(image_file_path))

            # Populate the project list with the new image as a top-level item
            self.populate_project_list()

            # Display the newly added image
            self.current_page_index = page_index
            self.show_current_page()
            self.status_bar.showMessage(f"Image '{file_path}' Loaded Successfully", 5000)

            # Enable actions once an image is loaded
            self.enable_actions_after_loading()

            self.logger.info(f"Image loaded and added to project: {file_path}")

        except Exception as e:
            self.show_error_message(f"Failed to load image '{file_path}': {e}")
            self.logger.error(f"Failed to load image '{file_path}': {e}", exc_info=True)

    def on_line_moved(self, line_item, new_line):
        """
        Handle the movement of a line item.

        :param line_item: LineItem object that was moved.
        :param new_line: QLineF object representing the new line position.
        """
        try:
            # Ensure the LineItem has the necessary attributes
            if not hasattr(line_item, 'line') or not hasattr(line_item, 'orientation') or not hasattr(line_item, 'image_filename'):
                self.logger.error("LineItem is missing required attributes ('line', 'orientation', 'image_filename').")
                self.show_error_message("Failed to move line: Internal error.")
                return

            # Capture the previous line position before the move
            # Assuming 'line_item.line' holds the previous line before updating to 'new_line'
            previous_line = line_item.line

            # Update the LineItem's line to the new position
            line_item.line = new_line  # Ensure LineItem has a setter for 'line'

            # Create MoveLineAction for undo functionality
            action = MoveLineAction(self, line_item, previous_line, new_line)
            self.graphics_view.undo_stack.append(action)
            self.graphics_view.redo_stack.clear()
            self.graphics_view.lineModified.emit()
            self.logger.info(f"Line moved from {previous_line} to {new_line}")

            # Update the lines dictionary in graphics_view
            image_filename = line_item.image_filename  # Direct attribute access

            if image_filename and image_filename in self.graphics_view.lines:
                # Define old and new tuples
                old_tuple = (previous_line, line_item.orientation)
                new_tuple = (new_line, line_item.orientation)

                # Access the list of lines for the current image
                lines_list = self.graphics_view.lines[image_filename]

                # Attempt to remove the old tuple
                try:
                    lines_list.remove(old_tuple)
                    self.logger.debug(f"Removed old line tuple {old_tuple} from lines[{image_filename}].")
                except ValueError:
                    self.logger.warning(f"Old line tuple {old_tuple} not found in lines[{image_filename}].")

                # Append the new tuple
                lines_list.append(new_tuple)
                self.logger.debug(f"Added new line tuple {new_tuple} to lines[{image_filename}].")
            else:
                self.logger.warning(f"Image filename '{image_filename}' not found in lines dictionary.")
        except AttributeError as ae:
            self.logger.error(f"LineItem does not have the required attribute: {ae}", exc_info=True)
            self.show_error_message("Failed to move line: Internal error.")
        except Exception as e:
            self.logger.error(f"Error handling line movement: {e}", exc_info=True)
            self.show_error_message(f"Failed to move line: {e}")

    def save_as(self):
        # Implement Save As functionality here
        if not self.last_csv_path or not os.path.exists(self.last_csv_path):
            self.show_error_message('No CSV file available to save. Please run OCR first.')
            return
        options = QFileDialog.Options()
        save_path, _ = QFileDialog.getSaveFileName(self, "Save CSV As", "", "CSV Files (*.csv);;All Files (*)", options=options)
        if save_path:
            try:
                with open(self.last_csv_path, 'r') as f_in, open(save_path, 'w') as f_out:
                    f_out.write(f_in.read())
                QMessageBox.information(self, 'Save Successful', 'CSV file saved successfully.')
            except Exception as e:
                self.logger.error(f"Error saving CSV: {e}")
                self.show_error_message(f'Failed to save CSV: {e}')
  
    def process_files(self, file_paths):
        """Process files that are dropped or opened and load them into the project."""
        try:
            for file_path in file_paths:
                if file_path is None:
                    self.show_error_message("Encountered a None file path.")
                    self.logger.error("Encountered a None file path in process_files.")
                    continue

                path = Path(file_path)
                if not path.exists():
                    self.show_error_message(f"File not found: {file_path}")
                    self.logger.error(f"File not found: {file_path}")
                    continue

                ext = path.suffix.lower()

                # Update recent files
                if file_path not in self.recent_files:
                    self.recent_files.insert(0, file_path)
                    if len(self.recent_files) > 5:
                        self.recent_files = self.recent_files[:5]
                    self.update_recent_files_menu()

                # Handle PDF files
                if ext in self.SUPPORTED_PDF_FORMATS:
                    self.load_pdf_file(str(path))
                
                # Handle supported image files
                elif ext in self.SUPPORTED_IMAGE_FORMATS:
                    self.load_image_file(str(path))
                
                # Unsupported file type
                else:
                    self.show_error_message(f"Unsupported file type: {file_path}")
                    self.logger.error(f"Unsupported file type: {file_path}")

        except Exception as e:
            self.show_error_message(f"An error occurred while processing files: {e}")
            self.logger.error(f"Error in process_files: {e}", exc_info=True)

    def load_image_file(self, file_name):
        """Handle loading of an image file."""
        try:
            self.clear_current_project()
            image = QImage(file_name)
            if image.isNull():
                raise ValueError("Failed to load image. File may be corrupted.")

            # Set the project folder based on the image name
            image_name = os.path.splitext(os.path.basename(file_name))[0]
            project_folder = os.path.join(os.getcwd(), image_name)
            os.makedirs(project_folder, exist_ok=True)
            self.project_folder = project_folder
            self.logger.info(f"Project folder set to: {self.project_folder}")

            # Convert QImage to PIL Image for consistency
            pil_image = Image.open(file_name).convert('RGB')
            self.pil_images = [pil_image]  # Initialize with the new image
            self.qimages = [self.pil_image_to_qimage(pil_image)]

            # Save the image as an image file in the temporary directory
            temp_dir = Path('temp_images')
            temp_dir.mkdir(exist_ok=True)
            image_file_path = temp_dir / f"{image_name}.png"
            pil_image.save(image_file_path, "PNG")
            self.image_file_paths = [str(image_file_path)]

            # Load the image into the graphics view
            self.graphics_view.load_image(self.qimages[0], filename=str(image_file_path))

            # Add the new project to the project explorer
            self.add_project_to_explorer(image_name, project_folder)

            # Select the first page of the new project
            self.select_first_page(image_name)

            # Enable actions once an image is loaded
            self.enable_actions_after_loading()

            # Update recent files list
            self.update_recent_files(file_name)

            self.logger.info(f"Image loaded and added to project: {file_name}")
            self.status_bar.showMessage(f"Image '{image_name}' Loaded Successfully", 5000)

        except Exception as e:
            self.show_error_message(f"Error loading image '{os.path.basename(file_name)}': {e}")
            self.logger.error(f"Error loading image from {file_name}: {e}", exc_info=True)

    def clear_current_project(self):
        """Clear all current project data."""
        try:
            self.pil_images.clear()
            self.qimages.clear()
            self.image_file_paths.clear()
            self.rectangles.clear()
            #self.scene.clear()
            self.project_list.clear()
            self.current_page_index = 0
            self.logger.info("Cleared current project data.")
        except Exception as e:
            self.logger.error(f"Error clearing project data: {e}", exc_info=True)
            self.show_error_message(f"Failed to clear current project: {e}")

    def load_pdf(self, file_path):
        """Load a PDF and convert each page into PIL and QImage formats using PyMuPDF."""
        self.status_bar.showMessage('Loading PDF...')
        QApplication.processEvents()

        try:
            # Import the PyMuPDF-based function
            from pdf_to_image import pdf_to_images

            # Convert PDF to list of PIL Images using PyMuPDF
            pil_images = pdf_to_images(pdf_path=file_path, dpi=400)
            if not pil_images:
                raise ValueError('No pages found in the PDF.')

            self.pil_images = pil_images  # Store PIL Images

            # Convert PIL Images to QImages
            self.qimages = [self.pil_image_to_qimage(pil_img) for pil_img in pil_images]

            self.current_page_index = 0  # Start from the first page

            # Save each page as an image file
            temp_dir = Path('temp_images')
            temp_dir.mkdir(exist_ok=True)
            self.image_file_paths = []
            for idx, pil_img in enumerate(self.pil_images):
                image_file_path = temp_dir / f"page_{idx + 1}.png"
                pil_img.save(image_file_path, "PNG")
                self.image_file_paths.append(str(image_file_path))

            # Populate the project list with page names as top-level items
            self.populate_project_list()

            # Display the first page initially
            self.show_current_page()
            self.status_bar.showMessage('PDF Loaded Successfully', 5000)

            # Enable actions once a PDF is loaded
            self.enable_actions_after_loading()

        except Exception as e:
            self.logger.error(f'Failed to load PDF: {e}', exc_info=True)
            QMessageBox.critical(self, 'Error', f'Failed to load PDF: {e}')
            self.status_bar.showMessage('Failed to load PDF', 5000)


    def populate_project_list(self):
        """Populate the project list with pages and images as top-level items."""
        try:
            self.project_list.clear()
            self.project_list.setHeaderHidden(False)
            self.project_list.setColumnCount(1)
            self.project_list.headerItem().setText(0, "Project Items")

            for idx in range(len(self.pil_images)):
                # Determine if the image is from a PDF or a standalone image
                if self.current_pdf_path and idx < len(self.pil_images):
                    item_label = f"Page {idx + 1}"
                else:
                    item_label = f"Image {idx + 1}"
                
                item = QTreeWidgetItem(self.project_list)
                item.setText(0, item_label)
                item.setFlags(item.flags() | Qt.ItemIsSelectable | Qt.ItemIsEnabled)
                self.project_list.addTopLevelItem(item)

                # Add cropped items as child items
                if idx in self.cropped_images:
                    for cropped_idx, cropped_path in enumerate(self.cropped_images[idx]):
                        cropped_item = QTreeWidgetItem(item)
                        cropped_item.setText(0, f"Cropped {cropped_idx + 1}: {Path(cropped_path).name}")
                        cropped_item.setFlags(cropped_item.flags() | Qt.ItemIsSelectable | Qt.ItemIsEnabled)
                        item.addChild(cropped_item)
            
            self.project_list.expandAll()
            self.logger.info("Project list populated with pages and images.")
        except Exception as e:
            self.logger.error(f"Error populating project list: {e}", exc_info=True)
            self.show_error_message(f"Failed to populate project list: {e}")

    def enable_actions_after_loading(self):
        """Enable actions that should be available after loading a PDF."""
        self.zoom_in_action.setEnabled(True)
        self.zoom_out_action.setEnabled(True)
        self.reset_zoom_action.setEnabled(True)
        self.fit_to_screen_action.setEnabled(True)
        self.detect_tables_action.setEnabled(True)
        self.edit_mode_action.setEnabled(True)
        self.cropping_mode_action.setEnabled(True)
        self.manual_table_detection_action.setEnabled(True)
        self.save_lines_action.setEnabled(True)
        self.logger.info("Enabled actions after loading PDF.")

    def update_page_label(self, page_index):
        """Update the page label or selection in the project list when the page changes."""
        try:
            self.project_list.setCurrentRow(page_index + 1)
        except Exception as e:
            self.logger.error(f"Error updating page label: {e}")

    def show_current_page(self):
        """Display the current page in the graphics view by loading it from memory."""
        try:
            # Check if the current page index is valid
            if not self.pil_images or self.current_page_index >= len(self.pil_images):
                self.logger.error(f'Invalid page index: {self.current_page_index}')
                return

            # Get the PIL image for the current page
            pil_image = self.pil_images[self.current_page_index]
            self.logger.debug(f"Displaying image for page {self.current_page_index + 1}")

            # Ensure the image is in RGBA format
            pil_image = pil_image.convert("RGBA")

            # Convert PIL image to bytes
            data = pil_image.tobytes("raw", "RGBA")
            qimage = QImage(data, pil_image.size[0], pil_image.size[1], QImage.Format_RGBA8888)

            if qimage is None:
                self.logger.error(f"Failed to convert PIL image to QImage for page {self.current_page_index}")
                return
            filename = self.image_file_paths[self.current_page_index]
            self.graphics_view.load_image(qimage, filename=filename)
            self.logger.info(f'Successfully displayed page {self.current_page_index + 1}')
            # Load existing rectangles if any
            self.graphics_view.clear_rectangles()
            page_rects = self.rectangles.get(self.current_page_index, [])
            for rect in page_rects:
                rect_item = QGraphicsRectItem(rect)
                pen = QPen(QColor(255, 0, 0), 2)
                rect_item.setPen(pen)
                self.graphics_view.scene().addItem(rect_item)
                self.graphics_view._rect_items.append(rect_item)

            # Load existing lines if any
            key = f"{self.current_page_index}_full"
            page_lines = self.lines.get(key, [])
            self.graphics_view.display_lines(page_lines, key=key)

            self.enable_actions_after_loading()

        except Exception as e:
            self.logger.error(f"Failed to display page {self.current_page_index}: {e}", exc_info=True)
            self.show_error_message(f"An error occurred while displaying page {self.current_page_index + 1}: {e}")

    def save_current_rectangles(self):
        rects = self.graphics_view.get_rectangles()
        self.rectangles[self.current_page_index] = rects
        self.logger.info(f"Rectangles saved for page {self.current_page_index + 1}")

    def save_lines(self):
        try:
            self.graphics_view.save_lines()
            self.logger.info("Lines saved successfully.")
        except Exception as e:
            self.logger.error(f"Error triggering save_lines: {e}", exc_info=True)
            self.show_error_message(f"Failed to save lines: {e}")

    def save_project(self):
        options = QFileDialog.Options()
        save_path, _ = QFileDialog.getSaveFileName(self, "Save Project As", "", "Project Files (*.proj);;All Files (*)", options=options)
        if save_path:
            project_data = {
                'current_pdf_path': self.current_pdf_path,
                'rectangles': self.rectangles,
                'lines': self.lines,
                'current_page_index': self.current_page_index,
                # Include any other relevant data
            }
            with open(save_path, 'wb') as f:
                pickle.dump(project_data, f)
            QMessageBox.information(self, 'Save Successful', 'Project saved successfully.')

    def load_project(self):
        options = QFileDialog.Options()
        load_path, _ = QFileDialog.getOpenFileName(self, "Open Project", "", "Project Files (*.proj);;All Files (*)", options=options)
        if load_path:
            with open(load_path, 'rb') as f:
                project_data = pickle.load(f)
            # Restore the state
            self.current_pdf_path = project_data['current_pdf_path']
            self.rectangles = project_data['rectangles']
            self.lines = project_data['lines']
            self.current_page_index = project_data['current_page_index']
            # Reload the PDF and annotations
            self.load_pdf(self.current_pdf_path)
            self.change_page(self.current_page_index)
            QMessageBox.information(self, 'Load Successful', 'Project loaded successfully.')

    def pil_image_to_qimage(self, pil_image):
        """Convert PIL Image to QImage."""
        try:
            if pil_image.mode == 'RGB':
                r, g, b = pil_image.split()
                image = Image.merge("RGB", (r, g, b))
                data = image.tobytes("raw", "RGB")
                qimage = QImage(data, image.width, image.height, QImage.Format_RGB888)
            elif pil_image.mode == 'RGBA':
                r, g, b, a = pil_image.split()
                image = Image.merge("RGBA", (r, g, b, a))
                data = image.tobytes("raw", "RGBA")
                qimage = QImage(data, image.width, image.height, QImage.Format_RGBA8888)
            elif pil_image.mode == 'L':
                # Convert grayscale to RGB
                image = pil_image.convert("RGB")
                r, g, b = image.split()
                data = image.tobytes("raw", "RGB")
                qimage = QImage(data, image.width, image.height, QImage.Format_RGB888)
            else:
                # For other modes, convert to RGBA
                image = pil_image.convert("RGBA")
                data = image.tobytes("raw", "RGBA")
                qimage = QImage(data, image.width, image.height, QImage.Format_RGBA8888)
            return qimage
        except Exception as e:
            self.logger.error(f"Error converting PIL Image to QImage: {e}", exc_info=True)
            self.show_error_message(f"Failed to convert image for display: {e}")
            return QImage()

    def initialize_ocr_engines(self):
        """Initializes the OCR engines."""
        # Update the status bar to inform the user about the initialization process
        self.status_bar.showMessage('Initializing OCR engines...')
        QApplication.processEvents()

        try:
            # Determine if GPU is available for OCR processing
            use_gpu = paddle.device.is_compiled_with_cuda()
            self.logger.debug(f"GPU available: {use_gpu}")

            # Initialize PaddleOCR engine
            self.logger.info("Initializing PaddleOCR engine.")
            self.ocr_engine = ocr_module.initialize_paddleocr(use_gpu)
            self.logger.debug("PaddleOCR engine initialized successfully.")

            # Initialize EasyOCR engine
            self.logger.info("Initializing EasyOCR engine.")
            self.easyocr_engine = ocr_module.initialize_easyocr(use_gpu)
            self.logger.debug("EasyOCR engine initialized successfully.")

            # Mark OCR engines as initialized
            self.ocr_initialized = True
            self.logger.info("Both OCR engines initialized successfully.")

            self.status_bar.showMessage('OCR engines initialized successfully.', 5000)

        except Exception as e:
            self.show_error_message(f'Failed to initialize OCR engines: {e}')
            self.logger.error(f'Failed to initialize OCR engines: {e}', exc_info=True)
            self.ocr_initialized = False
        finally:
            self.run_ocr_action.setEnabled(True)
            self.logger.debug("Run OCR button re-enabled after initialization attempt.")
    
    def run_ocr(self, selected_pages=None):
            """
            Initiates the OCR process by setting up necessary parameters,
            merging manual lines with automatic ones, initializing the OCRWorker thread,
            and handling user interactions.
    
            :param selected_pages: Optional list of page indices (zero-based) to process. If None, all pages are processed.
            """
            # Check if OCR engines are initialized
            if not self.ocr_initialized:
                self.initialize_ocr_engines()
    
            # Validate OCR engines
            if not self.ocr_initialized:
                self.show_error_message('Failed to initialize OCR engines.')
                self.logger.error('OCR engines not initialized.')
                return
            
            self.logger.debug(f"Received user_lines: {self.user_lines}")
    
            # Validate PDF file path
            if not self.current_pdf_path or not os.path.exists(self.current_pdf_path):
                self.show_error_message('Invalid or missing PDF file path.')
                self.logger.error('Invalid or missing PDF file path.')
                return
    
            if selected_pages is None:
                # If no specific pages are selected, process all pages
                self.logger.debug(f"Length of self.pil_images: {len(self.pil_images)}")
                selected_pages = list(range(len(self.pil_images)))
    
            # Ensure selected_pages is a list
            if not isinstance(selected_pages, list):
                self.logger.error(f"selected_pages is not a list: {selected_pages}, type: {type(selected_pages)}")
                self.show_error_message('Invalid page selection.')
                return
    
            # Ensure selected_pages is not empty
            self.logger.debug(f"Selected pages: {selected_pages}, type: {type(selected_pages)}")
            if not selected_pages:
                self.show_error_message('No pages selected for OCR.')
                self.logger.error('No pages selected for OCR.')
                return
    
            self.status_bar.showMessage('Running OCR...', 5000)
            QApplication.processEvents()
    
            # Save current rectangles and lines (Assuming these methods are defined elsewhere)
            self.save_current_rectangles()
            self.graphics_view.save_lines()
    
            # Initialize the progress bar
            if not self.progress_bar:
                self.progress_bar = QProgressBar()
                self.progress_bar.setMaximum(len(selected_pages))
                self.progress_bar.setValue(0)
                self.status_bar.addPermanentWidget(self.progress_bar)
            else:
                self.progress_bar.setMaximum(len(selected_pages))
                self.progress_bar.setValue(0)
                self.progress_bar.show()  # Ensure it's visible
    
            self.ocr_cancel_event = threading.Event()
    
            # Update the OCR action button to allow cancellation
            self.run_ocr_action.setText('Cancel OCR')
            self.ocr_running = True
    
            # Set up directories and output paths
            storedir = os.path.abspath("temp_gui")
            os.makedirs(storedir, exist_ok=True)
            output_csv = os.path.join(self.project_folder, "ocr_results.csv")
    
            # Retrieve the PDFGraphicsView instance
            pdf_graphics_view = self.findChild(PDFGraphicsView)
            if not pdf_graphics_view:
                self.show_error_message('Failed to locate PDFGraphicsView.')
                self.logger.error('PDFGraphicsView instance not found.')
                return
    
            # Use existing image paths
            self.logger.info("Preparing image list for OCR.")
            image_list = []
            for page_index in selected_pages:
                image_path = self.image_file_paths[page_index]
                if not os.path.exists(image_path):
                    self.logger.error(f"Image file does not exist: {image_path}")
                    self.show_error_message(f"Image file does not exist: {image_path}")
                    return
                image_list.append(image_path)
    
            # Detect tables automatically
            auto_TableMap = []
            for image_path in image_list:
                try:
                    auto_map = luminositybased.findTable(
                        image_path=image_path,
                        HorizontalState="border",
                        VerticalState="border",
                        horizontalgap_ratio=17/2077,
                        verticalgap_ratio=80/1474
                    )
                    auto_TableMap.append(auto_map)
                    self.logger.debug(f"Automatic TableMap for {image_path}: {auto_map}")
                except Exception as e:
                    self.logger.error(f"Error detecting tables in image {image_path}: {e}")
                    self.show_error_message(f"Table detection failed for {image_path}: {e}")
                    continue  # Skip to the next image
                
            # Get user-added lines
            user_lines = self.get_user_lines_for_pages(selected_pages)
            self.logger.debug(f"User-added lines: {user_lines}")
    
            # Validate user_lines structure
            for image, lines in user_lines.items():
                self.logger.debug(f"Processing image: {image}")
                self.logger.debug(f"Lines: {lines}")
                # 'lines' is expected to be a dict with 'horizontal' and 'vertical' lists
                if not isinstance(lines, dict):
                    self.logger.error(f"Lines for {image} should be a dict with 'horizontal' and 'vertical' keys.")
                    self.show_error_message(f"Invalid lines structure for {image}.")
                    continue
                if 'horizontal' not in lines or 'vertical' not in lines:
                    self.logger.error(f"Lines for {image} missing 'horizontal' or 'vertical' keys.")
                    self.show_error_message(f"Invalid lines structure for {image}.")
                    continue
                for y in lines['horizontal']:
                    if not isinstance(y, (float, int)):
                        self.logger.error(f"Invalid horizontal line position in {image}: {y}")
                        self.show_error_message(f"Invalid horizontal line position in {image}.")
                for x in lines['vertical']:
                    if not isinstance(x, (float, int)):
                        self.logger.error(f"Invalid vertical line position in {image}: {x}")
                        self.show_error_message(f"Invalid vertical line position in {image}.")
    
            self.logger.debug(f"Final user_lines to be passed to OCRWorker: {user_lines}")
    
            # Merge user and automatic lines
            combined_TableMap = self._merge_user_lines(auto_TableMap, user_lines, image_list)
            self.logger.debug(f"Combined TableMap: {combined_TableMap}")
    
            # Instantiate the OCRWorker thread with combined_TableMap
            self.ocr_worker = OCRWorker(
                pdf_file=self.current_pdf_path,
                storedir=storedir,
                output_csv=output_csv,
                ocr_cancel_event=self.ocr_cancel_event,
                ocr_engine=self.ocr_engine,
                easyocr_engine=self.easyocr_engine,
                combined_TableMap=combined_TableMap,  # Pass the combined_TableMap here
                image_list=image_list
            )
            # Connect OCRWorker signals to respective slots
            self.ocr_worker.ocr_progress.connect(self.on_ocr_progress)
            self.ocr_worker.ocr_time_estimate.connect(self.update_remaining_time_label)
            self.ocr_worker.ocr_completed.connect(self.on_ocr_completed)
            self.ocr_worker.ocr_error.connect(self.on_ocr_error)
    
            # Start the OCRWorker thread
            self.ocr_worker.start()
            self.logger.info("OCRWorker thread started.")
    
            # Update the OCR action button to allow cancellation
            self.run_ocr_action.triggered.disconnect(self.run_ocr)
            self.run_ocr_action.triggered.connect(self.cancel_ocr)


    def run_ocr_on_selected_pages(self):
        """Initiate OCR on user-selected pages."""
        try:
            total_pages = len(self.pil_images)  # Assuming self.pil_images contains all the pages
            if total_pages == 0:
                self.show_error_message("No pages available for OCR.")
                return

            # Open the page selection dialog
            dialog = PageSelectionDialog(self, total_pages)
            if dialog.exec_() == QDialog.Accepted:
                page_input = dialog.get_selected_pages()
                selected_pages = self.parse_page_selection(page_input, total_pages)
                if not selected_pages:
                    self.show_error_message("No valid pages selected for OCR.")
                    return
                
                # Show the "Run OCR" button now that pages are selected
                self.run_ocr_action.setVisible(True)

                # Run OCR on selected pages
                self.run_ocr(selected_pages)
        except Exception as e:
            self.logger.error(f"Error initiating OCR on selected pages: {e}", exc_info=True)
            self.show_error_message(f"An error occurred: {e}")

    def parse_page_selection(self, page_input, total_pages):
        """
        Parses the user's page selection input and returns a list of zero-based page indices.

        :param page_input: String input from the user (e.g., "1", "1-3", "1,3,5-7")
        :param total_pages: Total number of pages available
        :return: List of zero-based page indices
        """
        try:
            self.logger.debug(f"Parsing page selection input: '{page_input}'")
            if not isinstance(page_input, str):
                raise ValueError("Page input must be a string.")

            if not page_input.strip():
                self.logger.debug("No page input provided.")
                return []

            pages = set()
            for part in page_input.split(','):
                part = part.strip()
                if '-' in part:
                    start, end = part.split('-')
                    start = int(start)
                    end = int(end)
                    if start > end:
                        self.logger.warning(f"Ignoring invalid range '{part}'")
                        continue
                    # Convert to zero-based index
                    pages.update(range(start - 1, end))
                else:
                    page = int(part)
                    # Convert to zero-based index
                    pages.add(page - 1)

            # Filter out invalid page indices
            valid_pages = sorted([p for p in pages if 0 <= p < total_pages])
            self.logger.debug(f"Parsed pages: {valid_pages}")
            return valid_pages
        except Exception as e:
            self.logger.error(f"Error parsing page selection: {e}", exc_info=True)
            self.show_error_message(f"Invalid page selection format: {e}")
            return []


    def get_user_lines_for_pages(self, selected_pages):
        """
        Retrieves user-defined lines for the selected pages from the GUI.
        Converts QLineF objects to numerical positions.

        :param selected_pages: List of zero-based page indices.
        :return: Dictionary mapping image filenames to their respective manual lines.
        """
        user_lines = {}
        for page_index in selected_pages:
            if 0 <= page_index < len(self.image_file_paths):
                image_filename = os.path.basename(self.image_file_paths[page_index])
                lines = self.graphics_view.get_lines_for_image(image_filename)  # Returns list of (QLineF, orientation)
                
                manual_horizontal = []
                manual_vertical = []
                
                for line, orientation in lines:
                    if orientation == 'horizontal':
                        # Extract y-coordinate (average of y1 and y2)
                        y = (line.y1() + line.y2()) / 2
                        y = round(y, 2)  # Optional: Round for precision
                        manual_horizontal.append(y)
                        self.logger.debug(f"User added horizontal line: y={y}")
                    elif orientation == 'vertical':
                        # Extract x-coordinate (average of x1 and x2)
                        x = (line.x1() + line.x2()) / 2
                        x = round(x, 2)  # Optional: Round for precision
                        manual_vertical.append(x)
                        self.logger.debug(f"User added vertical line: x={x}")
                    else:
                        self.logger.warning(f"Unknown orientation: {orientation}")
                
                user_lines[image_filename] = {
                    'horizontal': manual_horizontal,
                    'vertical': manual_vertical
                }
                self.logger.debug(f"User lines for {image_filename}: {user_lines[image_filename]}")
        return user_lines

    def save_cropped_image(self, cropped_image, crop_rect):
        """Save the cropped image to disk and update internal structures."""
        try:
            if not self.project_folder:
                # Prompt the user to select a project folder
                self.project_folder = QFileDialog.getExistingDirectory(self, "Select Project Folder")
                if not self.project_folder:
                    raise ValueError("Project folder not selected.")
                self.logger.info(f"Project folder set to: {self.project_folder}")

            # Construct the path to save the cropped image
            cropped_image_dir = os.path.join(self.project_folder, 'cropped_images')
            os.makedirs(cropped_image_dir, exist_ok=True)
            cropped_image_filename = f"cropped_page_{self.current_page_index + 1}_{len(self.cropped_images.get(self.current_page_index, [])) + 1}.png"
            cropped_image_path = os.path.join(cropped_image_dir, cropped_image_filename)

            # Save the cropped image
            cropped_image.save(cropped_image_path)
            self.logger.info(f"Cropped image saved to {cropped_image_path}")

            # Add the cropped image to the cropped images dictionary under the current page
            if self.current_page_index not in self.cropped_images:
                self.cropped_images[self.current_page_index] = []
            self.cropped_images[self.current_page_index].append(cropped_image_path)

            # Determine the cropped index
            cropped_index = len(self.cropped_images[self.current_page_index])

            # Get the current image filename
            current_image_filename = self.image_file_paths[self.current_page_index]

            # Create and add a RectItem to the scene
            rect_item = RectItem(crop_rect, image_filename=current_image_filename)
            rect_item.setPen(QPen(QColor(255, 0, 0), 2))  # Red pen
            self.graphics_view.scene().addItem(rect_item)
            self._rect_items.append(rect_item)

            # Return the cropped image details
            return cropped_image_path, self.current_page_index, cropped_index

        except Exception as e:
            self.logger.error(f"Error saving cropped image: {e}", exc_info=True)
            self.show_error_message(f"Failed to save cropped image: {e}")
            return None, None, None

    def crop_image_pil(self, pil_image, rect):
        try:
            pixmap_item = self.graphics_view._pixmap_item
            if not pixmap_item:
                self.view.logger.error("No pixmap item found in graphics view.")
                raise ValueError("No image loaded in the graphics view.")

            # Map the rectangle from scene coordinates to pixmap coordinates
            mapped_rect = pixmap_item.mapFromScene(rect).boundingRect()

            pixmap_width = pixmap_item.pixmap().width()
            pixmap_height = pixmap_item.pixmap().height()

            image_width, image_height = pil_image.size

            scale_x = image_width / pixmap_width
            scale_y = image_height / pixmap_height

            scale = min(scale_x, scale_y)

            left = int(max(0, mapped_rect.left() * scale))
            top = int(max(0, mapped_rect.top() * scale))
            right = int(min(mapped_rect.right() * scale, image_width))
            bottom = int(min(mapped_rect.bottom() * scale, image_height))

            self.logger.debug(f"Cropping rectangle (pixels): Left={left}, Top={top}, Right={right}, Bottom={bottom}")

            if right > left and bottom > top:
                cropped_image = pil_image.crop((left, top, right, bottom))
                return cropped_image
            else:
                self.logger.error(f"Invalid crop dimensions: Left={left}, Top={top}, Right={right}, Bottom={bottom}")
                raise ValueError("Crop dimensions are out of bounds or invalid.")

        except Exception as e:
            self.logger.error(f"Error cropping image: {e}", exc_info=True)
            raise ValueError(f"Crop operation failed: {e}")

    def toggle_edit_mode(self):
        if self.edit_mode_action.isChecked():
            self.graphics_view.setDragMode(QGraphicsView.ScrollHandDrag)
            self.logger.debug("Edit mode enabled: Drag mode set to ScrollHandDrag")
        else:
            self.graphics_view.setDragMode(QGraphicsView.NoDrag)
            self.logger.debug("Edit mode disabled: Drag mode set to NoDrag")

    def toggle_cropping_mode(self):
        if self.cropping_mode_action.isChecked():
            self.graphics_view.enable_cropping_mode(True)
        else:
            self.graphics_view.enable_cropping_mode(False)

    def zoom_in(self):
        self.graphics_view.scale(1.2, 1.2)

    def zoom_out(self):
        self.graphics_view.scale(1 / 1.2, 1 / 1.2)

    def reset_zoom(self):
        """Reset the zoom level to 100%."""
        self.graphics_view.resetTransform()
        self.status_bar.showMessage('Zoom reset to 100%', 5000)

    def fit_to_screen(self):
        """Fit the current image to the screen."""
        self.graphics_view.fitInView(self.graphics_view._pixmap_item, Qt.KeepAspectRatio)
        self.status_bar.showMessage('Image fitted to screen', 5000)

    def normal_output_written(self, text):
        cursor = self.log_output.textCursor()
        cursor.movePosition(cursor.End)
        cursor.insertText(text)
        self.log_output.setTextCursor(cursor)
        self.log_output.ensureCursorVisible()

    def error_output_written(self, text):
        cursor = self.log_output.textCursor()
        cursor.movePosition(cursor.End)
        format = cursor.charFormat()
        format.setForeground(QColor('red'))
        cursor.setCharFormat(format)
        cursor.insertText(text)
        self.log_output.setTextCursor(cursor)
        self.log_output.ensureCursorVisible()

    def change_text_size(self, size):
        self.text_size = int(size)
        self.setStyleSheet(f"font-size: {self.text_size}px;")
        self.status_bar.showMessage(f'Text size changed to {size}px.', 5000)

    def display_table(self, table_data, low_confidence_results):
        """Display OCR results in a table view with low-confidence cells highlighted in red."""
        try:
            if not table_data:
                self.show_error_message("No data to display.")
                self.logger.warning("No data available in table_data.")
                return
            
            # Ensure all keys are integers
            if not all(isinstance(row, int) for row in table_data.keys()):
                raise TypeError("Row indices in table_data must be integers.")
            
            # Determine maximum row and column indices
            max_row = max(table_data.keys())
            max_col = max(
                max(cols.keys()) if isinstance(cols, dict) else 0 
                for cols in table_data.values()
            )
            
            # Initialize a QTableWidget
            table_widget = QTableWidget()
            table_widget.setRowCount(max_row + 1)
            table_widget.setColumnCount(max_col + 1)
            
            # # Set headers if available
            # headers = table_data.get(0, {})
            # for col in range(max_col + 1):
            #     header_text = headers.get(col, f"Column {col+1}")
            #     table_widget.setHorizontalHeaderItem(col, QTableWidgetItem(header_text))
            
            # Populate the table
            for row in range(1, max_row + 1):  # Start from 1 if row 0 is headers
                for col in range(max_col + 1):
                    text = table_data.get(row, {}).get(col, "")
                    item = QTableWidgetItem(text)
                    
                    # Check if this cell is in low_confidence_results
                    if (row, col) in low_confidence_results:
                        item.setBackground(QColor(255, 0, 0, 100))  # Semi-transparent red
                        item.setToolTip("Low confidence")
                    
                    table_widget.setItem(row, col, item)
            
            # Adjust table settings
            table_widget.resizeColumnsToContents()
            table_widget.resizeRowsToContents()
            table_widget.setAlternatingRowColors(True)
            table_widget.setSelectionBehavior(QTableWidget.SelectRows)
            table_widget.setEditTriggers(QTableWidget.NoEditTriggers)
            table_widget.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
            table_widget.setSortingEnabled(True)
            
            # Replace the existing table in 'Table View' tab
            table_view_index = self.output_tabs.indexOf(self.tableWidget)
            if table_view_index != -1:
                self.output_tabs.removeTab(table_view_index)
            
            self.output_tabs.addTab(table_widget, 'Table View')
            self.output_tabs.setCurrentWidget(table_widget)
            
            self.logger.info("OCR results displayed in table view successfully.")
        
        except Exception as e:
            self.logger.error(f"Error in display_table: {e}", exc_info=True)
            self.show_error_message(f"An error occurred while displaying the table: {e}")

    def show_error_message(self, message, detailed_message=None, title="Error", icon=QMessageBox.Critical):
        """Display an enhanced error message with optional details."""
        error_dialog = QMessageBox(self)
        error_dialog.setWindowTitle(title)
        error_dialog.setIcon(icon)
        error_dialog.setText(message)
        
        # Optional: Add a detailed message for additional context
        if detailed_message:
            error_dialog.setDetailedText(detailed_message)
        
        # Optional: Set the default buttons (OK button in this case)
        error_dialog.setStandardButtons(QMessageBox.Ok)
        
        # Add a custom stylesheet or set fixed size if needed
        error_dialog.setStyleSheet("QLabel{min-width: 250px; font-size: 24px;}")  # Customize the appearance
        
        error_dialog.exec_()

        # Optionally, log the error
        self.logger.error(f"Error displayed: {message}")
        if detailed_message:
            self.logger.error(f"Details: {detailed_message}")

    def on_ocr_completed(self, result):
        """
        Handles the completion of the OCR task in the GUI, including saving the results to a CSV,
        updating the GUI with performance statistics, and showing OCR quality information.
        """
        all_table_data, total, bad, easyocr_count, paddleocr_count, low_confidence_results, processing_time = result
        
        if self.current_pdf_path:
            default_csv_name = os.path.splitext(os.path.basename(self.current_pdf_path))[0] + '.csv'
            default_csv_path = os.path.join(self.project_folder, default_csv_name)
        else:
            default_csv_path = os.path.join(self.project_folder, 'ocr_results.csv')

        csv_file_path = default_csv_path
        try:
            ocr_module.write_results_to_csv(all_table_data, csv_file_path)
        except Exception as e:
            self.show_error_message(f"Failed to write CSV file: {e}")
            self.logger.error(f"Failed to write CSV file: {e}")
            return
        try:
            with open(csv_file_path, 'r', encoding='utf-8') as f:
                csv_content = f.read()
                self.csv_output.setPlainText(csv_content)
        except Exception as e:
            self.show_error_message(f"Failed to read CSV file: {e}")
            self.logger.error(f"Failed to read CSV file: {e}")

        self.status_bar.showMessage(f"OCR Completed. Results saved to {csv_file_path}", 5000)
        self.last_csv_path = csv_file_path 
        self.export_excel_action.setEnabled(True) 

        # Display the OCR results in the table view
        self.display_table(all_table_data, low_confidence_results)

        # Cleanup temporary files used during OCR
        try:
            if os.path.exists('temp_gui'):
                ocr_module.cleanup('temp_gui')
        except Exception as e:
            self.logger.warning(f"Could not cleanup 'temp_gui': {e}")

        try:
            if os.path.exists('temp_images'):
                ocr_module.cleanup('temp_images')
        except Exception as e:
            self.logger.warning(f"Could not cleanup 'temp_images': {e}")

        try:
            if os.path.exists('temp'):
                ocr_module.cleanup('temp')
        except Exception as e:
            self.logger.warning(f"Could not cleanup 'temp': {e}")

        # Remove the progress bar from the status bar
        if self.progress_bar:
            self.status_bar.removeWidget(self.progress_bar)
            self.progress_bar = None

        # Reset the remaining time label
        self.remaining_time_label.setText("Estimated remaining time: N/A")
        self.logger.debug("Remaining time label reset after OCR completion.")

        # Performance statistics
        num_pages = len(self.graphics_view.pdf_images)
        avg_time = processing_time / num_pages if num_pages else 0
        self.status_bar.showMessage(f'OCR Completed. Average time per page: {avg_time:.2f} seconds', 5000)

        # Quality statistics (for low-confidence results)
        if total > 0:
            percentage_low_confidence = (bad / total) * 100
            self.status_bar.showMessage(f"Low-confidence results (<80%): {percentage_low_confidence:.2f}% ({bad} items)", 5000)
        else:
            self.status_bar.showMessage("No OCR results to process.", 5000)

        # Log the OCR engine usage summary
        self.status_bar.showMessage(f'OCR Engine Usage - EasyOCR: {easyocr_count}, PaddleOCR: {paddleocr_count}', 5000)

        # Update the project explorer to show the new files
        self.update_project_explorer()

        # Reset the OCR running state and button text
        self.ocr_running = False
        self.run_ocr_action.setText('Run OCR')
        self.save_csv_action.setEnabled(True)
        self.run_ocr_action.setVisible(False)

    def on_ocr_progress(self, tasks_completed, total_tasks):
        self.progress_bar.setValue(tasks_completed)
        self.status_bar.showMessage(f'Processing OCR... ({tasks_completed}/{total_tasks})', 5000)

    def connect_ocr_signals(self):
        self.ocr_worker.ocr_progress.connect(self.on_ocr_progress)
        self.ocr_worker.ocr_time_estimate.connect(self.update_remaining_time_label)
        self.ocr_worker.ocr_completed.connect(self.on_ocr_completed)
        self.ocr_worker.ocr_error.connect(self.on_ocr_error)

    def disconnect_ocr_signals(self):
        self.ocr_worker.ocr_progress.disconnect(self.on_ocr_progress)
        self.ocr_worker.ocr_time_estimate.disconnect(self.update_remaining_time_label)
        self.ocr_worker.ocr_completed.disconnect(self.on_ocr_completed)
        self.ocr_worker.ocr_error.disconnect(self.on_ocr_error)

    def on_ocr_error(self, error_message):
        """
        Handles errors that occur during the OCR process.
        """
        self.status_bar.showMessage('OCR Failed', 5000)
        self.show_error_message(f'OCR Failed: {error_message}')
        if self.progress_bar:
            self.status_bar.removeWidget(self.progress_bar)
            self.progress_bar = None

        self.remaining_time_label.setText("Estimated remaining time: N/A")
        self.logger.debug("Remaining time label reset after OCR error.")
        #Disconnect OCR signals to prevent further slot invocations
        self.disconnect_ocr_signals()
        self.ocr_running = False
        self.run_ocr_action.setText('Run OCR')
        self.run_ocr_action.setVisible(False)

    def cancel_ocr(self):
        if self.ocr_running:
            self.ocr_cancel_event.set()
            self.logger.info("OCR cancellation requested by user.")
            self.status_bar.showMessage('OCR cancellation requested.', 5000)
            self.run_ocr_action.setText('Run OCR')
            self.ocr_running = False

            if self.progress_bar:
                self.progress_bar.hide()

            self.remaining_time_label.setText("Estimated remaining time: N/A")
            self.logger.debug("Remaining time label reset after OCR cancellation.")

            # Disconnect OCR signals to prevent further slot invocations
            self.disconnect_ocr_signals()

            # Reconnect the run OCR button
            self.run_ocr_action.triggered.disconnect(self.cancel_ocr)
            self.run_ocr_action.triggered.connect(self.run_ocr_on_selected_pages)
        else:
            self.logger.warning("Attempted to cancel OCR, but no OCR process is running.")
            self.show_error_message('No OCR process is currently running.')

    def cleanup_progress_bar(self):
        """Cleanup the progress bar after OCR completion or error."""
        if hasattr(self, 'progress_bar') and self.progress_bar:
            self.status_bar.removeWidget(self.progress_bar)
            self.progress_bar = None
        self.run_ocr_action.setText('Run OCR')
        self.ocr_running = False
        self.run_ocr_action.triggered.disconnect(self.cancel_ocr)
        self.run_ocr_action.triggered.connect(self.run_ocr_on_selected_pages)

    def save_csv(self):
        # Read data from the tableWidget and write to CSV
        row_count = self.tableWidget.rowCount()
        column_count = self.tableWidget.columnCount()

        with open(self.last_csv_path, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            for row in range(row_count):
                row_data = []
                for column in range(column_count):
                    item = self.tableWidget.item(row, column)
                    if item is not None:
                        row_data.append(item.text())
                    else:
                        row_data.append('')
                writer.writerow(row_data)
        self.status_bar.showMessage(f'CSV saved: {self.last_csv_path}', 5000)

    def export_to_excel(self):
        if self.last_csv_path and os.path.exists(self.last_csv_path):
            excel_file_path, _ = QFileDialog.getSaveFileName(
                self, "Save Excel File", self.last_csv_path.replace('.csv', '.xlsx'),
                "Excel Files (*.xlsx);;All Files (*)")
            if excel_file_path:
                try:
                    df = pd.read_csv(self.last_csv_path)
                    df.to_excel(excel_file_path, index=False)
                    QMessageBox.information(self, 'Export Successful', 'CSV exported to Excel successfully.')
                except Exception as e:
                    self.show_error_message(f'Failed to export CSV to Excel: {e}')
        else:
            self.show_error_message('No CSV file available to export.')

    def update_project_list(self, pdf_path, page_index, cropped_index, cropped_image_path):
        try:
            pdf_name = os.path.splitext(os.path.basename(pdf_path))[0]
            self.logger.info(f"Updating project list for PDF '{pdf_name}', page_index={page_index}, cropped_index={cropped_index}, image_path={cropped_image_path}")

            if None in (pdf_name, page_index, cropped_index, cropped_image_path):
                self.logger.warning("Invalid data received for updating project list.")
                return

            # Find or create the PDF project item
            project_item = None
            for i in range(self.project_list.topLevelItemCount()):
                item = self.project_list.topLevelItem(i)
                if item.text(0) == pdf_name:
                    project_item = item
                    break
            if not project_item:
                project_item = QTreeWidgetItem(self.project_list)
                project_item.setText(0, pdf_name)
                project_item.setFlags(project_item.flags() | Qt.ItemIsSelectable | Qt.ItemIsEnabled)
                self.logger.info(f"Created new project item: {pdf_name}")

            # Find or create the page item under the project
            page_item = None
            page_label = f"Page {page_index + 1} of '{pdf_name}'"
            for i in range(project_item.childCount()):
                child = project_item.child(i)
                if child.text(0) == page_label:
                    page_item = child
                    break
            if not page_item:
                page_item = QTreeWidgetItem(project_item)
                page_item.setText(0, page_label)
                page_item.setFlags(page_item.flags() | Qt.ItemIsSelectable | Qt.ItemIsEnabled)
                self.logger.info(f"Created new page item: {page_label}")

            # Add the cropped image under the page
            cropped_item_text = f"Cropped {cropped_index + 1}: {os.path.basename(cropped_image_path)}"
            cropped_item = QTreeWidgetItem(page_item)
            cropped_item.setText(0, cropped_item_text)
            cropped_item.setFlags(cropped_item.flags() | Qt.ItemIsSelectable | Qt.ItemIsEnabled)
            page_item.addChild(cropped_item)
            page_item.setExpanded(True)  # Expand to show the new child
            self.logger.info(f"Added cropped image to project list: {cropped_image_path}")

            # Optionally, scroll to the new item
            self.project_list.scrollToItem(cropped_item)

        except Exception as e:
            self.logger.error(f"Error updating project list: {e}", exc_info=True)
            self.show_error_message(f"Failed to update project list: {e}")

    def update_project_explorer(self):
        """Refresh the project explorer to reflect current project folder contents."""
        try:
            self.project_list.clear()

            # Check if project_folder is a valid directory
            if isinstance(self.project_folder, str) and os.path.exists(self.project_folder):
                # Use the current PDF name as the project name
                pdf_name = os.path.splitext(os.path.basename(self.current_pdf_path))[0]

                # Create the top-level project item in the project list
                project_item = QTreeWidgetItem(self.project_list)
                project_item.setText(0, pdf_name)
                project_item.setFlags(project_item.flags() | Qt.ItemIsSelectable | Qt.ItemIsEnabled)

                # Add pages based on image file paths
                image_dir = os.path.join(self.project_folder, 'temp_images')
                if os.path.exists(image_dir):
                    image_files = sorted(os.listdir(image_dir))
                    for page_index, image_file in enumerate(image_files):
                        page_item = QTreeWidgetItem(project_item)
                        page_item.setText(0, f"Page {page_index + 1}")
                        page_item.setData(0, Qt.UserRole, os.path.join(image_dir, image_file))
                        page_item.setFlags(page_item.flags() | Qt.ItemIsSelectable | Qt.ItemIsEnabled)

                    # Optionally, expand the project to show pages
                    project_item.setExpanded(True)
                else:
                    self.logger.warning(f"Image directory not found in project folder: {image_dir}")

                self.logger.info(f"Project explorer updated for {pdf_name}.")
            else:
                raise FileNotFoundError(f"Project folder does not exist or is invalid: {self.project_folder}")

        except Exception as e:
            self.logger.error(f"Error updating project explorer: {e}", exc_info=True)
            self.show_error_message(f"Failed to update project explorer: {e}")

    def add_project_to_explorer(self, pdf_name, project_folder):
        try:
            # Create the top-level project item
            project_item = QTreeWidgetItem(self.project_list)
            project_item.setText(0, pdf_name)
            project_item.setFlags(project_item.flags() | Qt.ItemIsSelectable | Qt.ItemIsEnabled)

            # Add pages to the project item
            image_dir = os.path.join(project_folder, 'temp_images')
            if os.path.exists(image_dir):
                image_files = sorted(os.listdir(image_dir))
                for page_index, image_file in enumerate(image_files):
                    page_item = QTreeWidgetItem(project_item)
                    page_item.setText(0, f"Page {page_index + 1}")
                    page_item.setData(0, Qt.UserRole, os.path.join(image_dir, image_file))
                    page_item.setFlags(page_item.flags() | Qt.ItemIsSelectable | Qt.ItemIsEnabled)

                # Expand the project item
                project_item.setExpanded(True)
            else:
                self.logger.warning(f"Image directory not found in project folder: {image_dir}")

            self.logger.info(f"Project '{pdf_name}' added to the explorer.")
        except Exception as e:
            self.logger.error(f"Error adding project to explorer: {e}", exc_info=True)
            self.show_error_message(f"Failed to add project to explorer: {e}")

    def display_csv_as_table(self, csv_path):
        """Display the CSV file as a table in the output dock."""
        try:
            self.logger.info(f"Displaying CSV as table: {csv_path}")

            # Check if CSV exists
            if not os.path.exists(csv_path):
                raise FileNotFoundError(f"CSV file not found: {csv_path}")

            # Read CSV data
            with open(csv_path, 'r', newline='', encoding='utf-8') as csvfile:
                reader = csv.reader(csvfile)
                data = list(reader)

            if not data:
                raise ValueError("CSV file is empty.")

            headers = data[0]
            rows = data[1:]

            # Create QTableWidget
            table_widget = QTableWidget()
            table_widget.setRowCount(len(rows))
            table_widget.setColumnCount(len(headers))
            table_widget.setHorizontalHeaderLabels(headers)

            # Populate table
            for row_idx, row in enumerate(rows):
                for col_idx, cell in enumerate(row):
                    item = QTableWidgetItem(cell)
                    table_widget.setItem(row_idx, col_idx, item)

            # Enhance table appearance
            table_widget.resizeColumnsToContents()
            table_widget.resizeRowsToContents()
            table_widget.setAlternatingRowColors(True)
            table_widget.setSelectionBehavior(QTableWidget.SelectRows)
            table_widget.setEditTriggers(QTableWidget.NoEditTriggers)
            table_widget.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
            table_widget.setSortingEnabled(True)

            # Remove existing widget in 'CSV Output' tab and add the new table
            csv_output_index = self.output_tabs.indexOf(self.csv_output)
            if csv_output_index != -1:
                self.output_tabs.removeTab(csv_output_index)
            
            self.output_tabs.addTab(table_widget, 'CSV Output')
            self.output_tabs.setCurrentWidget(table_widget)

            self.logger.info("CSV displayed as table successfully.")

        except Exception as e:
            self.logger.error(f"Error displaying CSV as table: {e}", exc_info=True)
            self.show_error_message(f"An error occurred while displaying the table: {e}")

    def cleanup_temp_images(self):
        """Delete all temporary directories and their contents."""
        temp_dirs = ['temp_images', 'temp_gui']
        for dir_name in temp_dirs:
            temp_dir = Path(dir_name)
            if temp_dir.exists() and temp_dir.is_dir():
                try:
                    shutil.rmtree(temp_dir, ignore_errors=True)
                    self.logger.info(f"Deleted temporary directory: {temp_dir}")
                except Exception as e:
                    self.logger.error(f"Failed to delete temporary directory {temp_dir}: {e}", exc_info=True)

    def closeEvent(self, event):
        self.cleanup_temp_images()
        event.accept()

def main():
    configure_logging()
    logger = logging.getLogger(__name__)
    logger.info("Application started.")
 
    sys.excepthook = exception_hook

    app = QApplication(sys.argv)

    try:
        with open("styles.qss", "r", encoding='utf-8') as style_file:
            app.setStyleSheet(style_file.read())
            logger.info("Stylesheet applied successfully.")
    except FileNotFoundError:
        logger.warning("Style file 'styles.qss' not found. Proceeding without styles.")
    except Exception as e:
        logger.error(f"Unexpected error while loading stylesheet: {e}", exc_info=True)
        QMessageBox.critical(
            None,
            "Error",
            f"An unexpected error occurred while loading the stylesheet:\n{e}"
        )
        sys.exit(1)

    try:
        window = OCRApp()
        window.show()
        logger.info("Main window initialized and shown successfully.")
    except Exception as e:
        logger.critical(f"Failed to initialize the main window: {e}", exc_info=True)
        QMessageBox.critical(
            None,
            "Critical Error",
            f"Failed to initialize the main window:\n{e}"
        )
        sys.exit(1)

    try:
        signal.signal(signal.SIGINT, signal.SIG_DFL)
    except Exception as e:
        logger.warning(f"Failed to set SIGINT handler: {e}")

    try:
        logger.info("Entering the main event loop.")
        sys.exit(app.exec_())
        window.save_recent_files()
        sys.exit(exit_code)
    except Exception as e:
        logger.critical(f"An unexpected error occurred during execution: {e}", exc_info=True)
        QMessageBox.critical(
            None,
            "Critical Error",
            f"An unexpected error occurred during execution:\n{e}"
        )
        sys.exit(1)

if __name__ == '__main__':
    main()
