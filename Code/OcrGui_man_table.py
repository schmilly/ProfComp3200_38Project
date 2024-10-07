# Standard library imports
import sys
import os
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
from PyPDF2 import PdfFileReader
import PyPDF2
import json

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
    QDialog, QUndoCommand, QGraphicsItem
)
from PyQt5.QtGui import QPixmap, QImage, QPen, QColor, QPainter, QFont, QDragEnterEvent, QDropEvent, QCursor 
from PyQt5.QtCore import Qt, QRectF, QObject, pyqtSignal, QLineF, QThread, QPointF, QSizeF
from pdf2image import convert_from_path
from PIL import Image
from logging.handlers import RotatingFileHandler

# Local imports
from ocr_pipe import run_ocr_pipeline
import ocr_pipe as rtr
import luminosity_table_detection as ltd


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
    moved = pyqtSignal(QLineF)  # Signal emitted when the line is moved

    def __init__(self, line, orientation='horizontal', parent=None):
        super().__init__(parent)
        self.logger = logging.getLogger(__name__)  # Initialize the logger
        self.orientation = orientation  # 'horizontal' or 'vertical'
        self._pen = QPen(QColor(0, 0, 255), 1, Qt.SolidLine)  # Blue pen, 1 pixel wide
        self.setPen(self._pen)
        self.setFlags(
            QGraphicsObject.ItemIsSelectable |
            QGraphicsObject.ItemIsMovable |
            QGraphicsObject.ItemSendsGeometryChanges
        )
        self.setAcceptHoverEvents(True)
        self.line = QLineF(line)  # Store the line as an attribute

    def boundingRect(self):
        pen_width = self._pen.width()
        extra = pen_width / 2.0
        return QRectF(self.line.p1(), self.line.p2()).normalized().adjusted(-extra, -extra, extra, extra)

    def paint(self, painter, option, widget=None):
        try:
            painter.setPen(self._pen)
            painter.drawLine(self.line)
        except Exception as e:
            self.logger.error(f"Error in LineItem paint: {e}", exc_info=True)

    def setPen(self, pen):
        self._pen = pen
        self.update()

    def itemChange(self, change, value):
        if change == QGraphicsObject.ItemPositionChange:
            new_pos = value
            delta = new_pos - self.pos()
            # Update the line position based on orientation
            if self.orientation == 'horizontal':
                new_line = QLineF(
                    self.line.p1().x(),
                    self.line.p1().y() + delta.y(),
                    self.line.p2().x(),
                    self.line.p2().y() + delta.y()
                )
                # Prevent horizontal movement
                new_pos.setX(self.pos().x())
            elif self.orientation == 'vertical':
                new_line = QLineF(
                    self.line.p1().x() + delta.x(),
                    self.line.p1().y(),
                    self.line.p2().x() + delta.x(),
                    self.line.p2().y()
                )
                # Prevent vertical movement
                new_pos.setY(self.pos().y())
            else:
                new_line = QLineF(
                    self.line.p1().x() + delta.x(),
                    self.line.p1().y() + delta.y(),
                    self.line.p2().x() + delta.x(),
                    self.line.p2().y() + delta.y()
                )
            self.line = new_line
            self.moved.emit(new_line)
            self.update()
            return new_pos
        return super().itemChange(change, value)

class RectItem(QGraphicsObject):
    moved = pyqtSignal(QRectF)

    def __init__(self, rect, parent=None):
        super().__init__(parent)
        self.logger = logging.getLogger(__name__) 
        self._rect = QRectF(rect)
        self._pen = QPen(QColor(255, 0, 0), 2)  # Red pen
        self.setFlags(
            QGraphicsItem.ItemIsSelectable |
            QGraphicsItem.ItemIsMovable |
            QGraphicsItem.ItemSendsGeometryChanges
        )

    def boundingRect(self):
        pen_width = self._pen.width()
        extra = pen_width / 2.0
        return self._rect.normalized().adjusted(-extra, -extra, extra, extra)

    def paint(self, painter, option, widget=None):
        try:
            painter.setPen(self._pen)
            painter.drawRect(self._rect)
        except Exception as e:
            self.logger.error(f"Error in RectItem paint: {e}", exc_info=True)

    def setRect(self, rect):
        self.prepareGeometryChange()
        self._rect = QRectF(rect)
        self.update()

    def rect(self):
        return self._rect

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionChange:
            # Calculate the movement delta
            delta = value - self.pos()
            # Update the rectangle position
            new_rect = self._rect.translated(delta)
            self.setRect(new_rect)
            self.moved.emit(new_rect)
            return value
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

class AddRectangleAction(Action):
    def __init__(self, view, rect_item):
        self.view = view
        self.rect_item = rect_item

    def undo(self):
        self.view.scene().removeItem(self.rect_item)
        self.view._rect_items.remove(self.rect_item)

    def redo(self):
        self.view.scene().addItem(self.rect_item)
        self.view._rect_items.append(self.rect_item)

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

class OCRWorker(QThread):
    ocr_progress = pyqtSignal(int, int)
    ocr_completed = pyqtSignal(object)
    ocr_error = pyqtSignal(str)

    def __init__(self, pdf_file, storedir, output_csv, ocr_cancel_event):
        super().__init__()
        self.pdf_file = pdf_file
        self.storedir = storedir
        self.output_csv = output_csv
        self.ocr_cancel_event = ocr_cancel_event

    def run(self):
        try:
            # Run OCR processing here
            results = run_ocr_pipeline(
                self.pdf_file,
                self.storedir,
                self.output_csv,
                self.ocr_progress,
                self.ocr_cancel_event
            )
            # Emit completion signal with results
            self.ocr_completed.emit(results)
        except Exception as e:
            # Capture the exception traceback
            tb = traceback.format_exc()
            self.logger.error(f"Error in OCRWorker: {e}\n{tb}")
            # Emit error signal with the exception message
            self.ocr_error.emit(str(e))

    def cancel(self):
        """Method to cancel the OCR process."""
        self.ocr_cancel_event.set()
        self.logger.info("OCR cancellation requested.")

class PDFGraphicsView(QGraphicsView):
    rectangleSelected = pyqtSignal(QRectF)
    lineModified = pyqtSignal()
    croppedImageCreated = pyqtSignal(int, int, str)
    logger = logging.getLogger(__name__)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
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
        self.lines = {}

        try:
            self.rectangleSelected.connect(self.get_main_window().on_rectangle_selected)
            self.lineModified.connect(self.get_main_window().on_line_modified)
        except Exception as e:
            self.logger.error(f"Error connecting signals: {e}")

    def get_main_window(self):
        """Traverse the parent hierarchy to get the QMainWindow (OCRApp) instance."""
        try:
            parent = self.parent()
            while parent is not None:
                if isinstance(parent, QMainWindow):  # Check if the parent is the QMainWindow
                    return parent
                parent = parent.parent()
            raise RuntimeError("Main window (QMainWindow) not found in the parent hierarchy.")
        except Exception as e:
            self.logger.error(f"Error in get_main_window: {e}")
            raise

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
    
    def add_line(self, start_point, end_point, orientation=None):
        """Add a straight line from start_point to end_point, extending from edge to edge."""
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
            if self._pixmap_item:
                pixmap_rect = self._pixmap_item.pixmap().rect()
            else:
                pixmap_rect = self.sceneRect()

            if orientation == 'vertical':
                x = start_point.x()
                start_point = QPointF(x, pixmap_rect.top())
                end_point = QPointF(x, pixmap_rect.bottom())
            elif orientation == 'horizontal':
                y = start_point.y()
                start_point = QPointF(pixmap_rect.left(), y)
                end_point = QPointF(pixmap_rect.right(), y)

            line = QLineF(start_point, end_point)
            line_item = LineItem(line, orientation=orientation)
            self.scene().addItem(line_item)
            self._line_items.append(line_item)

            # Connect the moved signal
            line_item.moved.connect(lambda new_line, item=line_item: self.on_line_moved(item, new_line))
            
            # Create and push AddLineAction to undo stack
            main_window = self.get_main_window()
            if main_window:
                action = AddLineAction(main_window, line_item)
                self.undo_stack.append(action)
                self.redo_stack.clear()
                self.lineModified.emit()
                self.logger.info(f"Line added from {start_point} to {end_point}, Orientation: {orientation}")
            else:
                self.logger.error("Main window instance not found. Cannot add line.")
        except Exception as e:
            self.logger.error(f"Error adding line: {e}", exc_info=True)
            self.get_main_window().show_error_message(f"Failed to add line: {e}")

    
    def remove_line(self, line_item):
        """Remove a specified line_item."""
        try:
            if line_item in self._line_items:
                main_window = self.get_main_window()
                if main_window:
                    self.scene().removeItem(line_item)
                    self._line_items.remove(line_item)

                    # Create and push RemoveLineAction to undo stack
                    action = RemoveLineAction(main_window, line_item)
                    self.undo_stack.append(action)
                    self.redo_stack.clear()  # Clear redo stack on new action

                    self.lineModified.emit()

                    self.logger.info("Line removed.")
                else:
                    self.logger.error("Main window instance not found. Cannot remove line.")
                    self.get_main_window().show_error_message("Internal Error: Main window not found.")
            else:
                self.logger.warning("Attempted to remove a non-existent line.")
        except Exception as e:
            self.logger.error(f"Error removing line: {e}", exc_info=True)
            self.get_main_window().show_error_message(f"Failed to remove line: {e}")

    def add_rectangle(self, rect):
        """Add a rectangle to the scene."""
        try:
            rect_item = RectItem(rect)
            self.scene().addItem(rect_item)
            self._rect_items.append(rect_item)

            # Connect the moved signal
            rect_item.moved.connect(lambda new_rect, item=rect_item: self.on_rect_moved(item, new_rect))

            # Create and push AddRectangleAction to undo stack
            action = AddRectangleAction(self, rect_item)
            self.undo_stack.append(action)
            self.redo_stack.clear()  # Clear redo stack on new action

            self.logger.info(f"Rectangle added: {rect}")
        except Exception as e:
            self.logger.error(f"Error adding rectangle: {e}", exc_info=True)
            self.get_main_window().show_error_message(f"Failed to add rectangle: {e}")

    def on_rect_moved(self, rect_item, new_rect):
        """Handle the movement of a rectangle item."""
        try:
            # Capture the previous rectangle position
            previous_rect = rect_item._previous_rect
            # Create MoveRectangleAction
            action = MoveRectangleAction(self, rect_item, previous_rect, new_rect)
            self.undo_stack.append(action)
            self.redo_stack.clear()
            self.lineModified.emit()
            self.logger.info(f"Rectangle moved from {previous_rect} to {new_rect}")
        except Exception as e:
            self.logger.error(f"Error handling rectangle movement: {e}", exc_info=True)
            self.get_main_window().show_error_message(f"Failed to move rectangle: {e}")

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

                self.logger.info("Rectangle removed.")
            else:
                self.logger.warning("Attempted to remove a non-existent rectangle.")
        except Exception as e:
            self.logger.error(f"Error removing rectangle: {e}", exc_info=True)
            self.get_main_window().show_error_message(f"Failed to remove rectangle: {e}")

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
   
    def load_image(self, qimage):
        """Load a QImage into the scene."""
        try:
            self.scene().clear()
            qt_pixmap = QPixmap.fromImage(qimage)
            if qt_pixmap.isNull():
                raise ValueError("Failed to convert QImage to QPixmap.")
            self._pixmap_item = QGraphicsPixmapItem(qt_pixmap)
            self.scene().addItem(self._pixmap_item)
            self.fitInView(self._pixmap_item, Qt.KeepAspectRatio)
            self._rect_items.clear()
            self._line_items.clear()

            # Reset any transformations
            self._pixmap_item.setRotation(0)
            self._pixmap_item.setScale(1)

            self.logger.info("Image loaded into PDFGraphicsView successfully.")
        except Exception as e:
            self.logger.error(f"Error loading image into scene: {e}", exc_info=True)
            self.get_main_window().show_error_message(f"An error occurred while loading image: {e}")

    def mousePressEvent(self, event):
        try:
            if event.button() == Qt.LeftButton:
                scene_pos = self.mapToScene(event.pos())
                if self.adding_vertical_line or self.adding_horizontal_line:
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
            self.get_main_window().show_error_message(f"An error occurred: {e}")

    def mouseMoveEvent(self, event):
        try:
            if hasattr(self, '_start_pos') and self._start_pos:
                current_pos = self.mapToScene(event.pos())
                if hasattr(self, '_temp_line') and self._temp_line:
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
        except Exception as e:
            self.logger.error(f"Error in mouseMoveEvent: {e}")
            self.get_main_window().show_error_message(f"An error occurred: {e}")

    def mouseReleaseEvent(self, event):
        try:
            if event.button() == Qt.LeftButton:
                if hasattr(self, '_temp_line') and self._temp_line:
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
                        self.get_main_window().add_vertical_line_action.setChecked(False)
                        self.get_main_window().add_horizontal_line_action.setChecked(False)
                elif hasattr(self, '_temp_rect_item') and self._temp_rect_item:
                    # Finalize rectangle
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
            self.logger.error(f"Error in mouseReleaseEvent: {e}", exc_info=True)
            self.get_main_window().show_error_message(f"An error occurred: {e}")

    def wheelEvent(self, event):
        try:
            if event.modifiers() & Qt.ControlModifier:
                angle = event.angleDelta().y()
                if angle > 0:
                    self.get_main_window.zoom_in()
                elif angle < 0:
                    self.get_main_window.zoom_out()
                event.accept()
            else:
                super().wheelEvent(event)
        except Exception as e:
            self.logger.error(f"Error in wheelEvent: {e}", exc_info=True)
            super().wheelEvent(event)

    def status_bar_message(self, message, duration=5000):
        """Helper method to display messages in the status bar."""
        self.get_main_window().status_bar.showMessage(message, duration)
    
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
            self.get_main_window().show_error_message(f"Failed to add rectangle: {e}")

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
                self.next_page()
            elif event.key() == Qt.Key_Left:
                self.previous_page()
            else:
                super().keyPressEvent(event)
        except Exception as e:
            self.logger.error(f"Error in keyPressEvent: {e}")
            self.get_main_window().show_error_message(f"An error occurred: {e}")

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
            self.get_main_window().show_error_message(f"Failed to undo: {e}")

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
            self.get_main_window().show_error_message(f"Failed to redo: {e}")

    def get_rectangles(self):
        return [item.rect() for item in self._rect_items]

    def clear_rectangles(self):
        for item in self._rect_items:
            self.scene().removeItem(item)
        self._rect_items.clear()

    def enable_cropping_mode(self, enabled):
        self.cropping_mode = enabled
        if enabled:
            self.setDragMode(QGraphicsView.NoDrag)
        else:
            self.setDragMode(QGraphicsView.ScrollHandDrag)

    def display_lines(self, lines, key=None):
        """Display detected table lines on the image."""
        try:
            if not hasattr(self, '_pixmap_item') or not self._pixmap_item:
                raise RuntimeError("No image loaded in PDFGraphicsView to display lines on.")

            pen = QPen(QColor(0, 255, 0), 1)  # Green lines, 1 pixel wide
            key = key or f"{self.current_page_index}_full"
            self.logger.debug(f"Displaying lines for key '{key}' with {len(lines)} lines.")

            # Clear existing lines for the key
            existing_lines = self.lines.get(key, [])
            for line in existing_lines:
                for item in self._line_items.copy():  # Use copy to avoid modification during iteration
                    if item.line == line:
                        self.scene().removeItem(item)
                        self._line_items.remove(item)
                        break

            # Add new lines
            self.lines[key] = lines
            for line in lines:
                line_item = LineItem(line)
                line_item.setPen(pen)  # Use the setPen method
                orientation = 'horizontal' if line.p1().y() == line.p2().y() else 'vertical'
                line_item.orientation = orientation  # Set the orientation
                self.scene().addItem(line_item)
                self._line_items.append(line_item)

                # Connect the moved signal
                line_item.moved.connect(lambda new_line, item=line_item: self.on_line_moved(item, new_line))

            self.logger.info(f"Displayed {len(lines)} table lines for key '{key}'.")
        except Exception as e:
            self.logger.error(f"Error displaying table lines: {e}", exc_info=True)
            self.get_main_window().show_error_message(f"Failed to display table lines: {e}")

    def get_lines(self):
        return [item.line for item in self._line_items]

    def clear_lines(self):
        """Clear all the lines from the scene."""
        for line_item in self._line_items:
            self.scene().removeItem(line_item)
        self._line_items.clear()

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            # Check if any of the URLs is a supported file type
            for url in event.mimeData().urls():
                if url.isLocalFile():
                    file_path = url.toLocalFile()
                    _, ext = os.path.splitext(file_path)
                    if ext.lower() in self.get_main_window().SUPPORTED_PDF_FORMATS.union(self.get_main_window().SUPPORTED_IMAGE_FORMATS):
                        event.acceptProposedAction()
                        return
        event.ignore()

    def dropEvent(self, event):
        try:
            if event.mimeData().hasUrls():
                for url in event.mimeData().urls():
                    if url.isLocalFile():
                        file_path = url.toLocalFile()
                        mime_type, _ = mimetypes.guess_type(file_path)
                        if not mime_type:
                            _, ext = os.path.splitext(file_path)
                            ext = ext.lower()
                            if ext == '.pdf':
                                mime_type = 'application/pdf'
                            elif ext in ['.png', '.jpg', '.jpeg']:
                                mime_type = 'image/' + ext.lstrip('.')
                        if mime_type == 'application/pdf' or mime_type.startswith('image/'):
                            self.get_main_window().process_files([file_path])
                            self.get_main_window().update_recent_files(file_path)
                        else:
                            self.get_main_window().show_error_message("Invalid file type. Only PDF or image files supported.")
        except Exception as e:
            self.get_main_window().show_error_message(f"An error occurred while dropping files: {e}")
            self.logger.error(f"Error in dropEvent: {e}", exc_info=True)

class OCRApp(QMainWindow):
    ocr_completed = pyqtSignal(object)
    ocr_progress = pyqtSignal(int, int)
    ocr_error = pyqtSignal(str)
    croppedImageCreated = pyqtSignal(int, int, str)
    SUPPORTED_IMAGE_FORMATS = {'.png', '.jpg', '.jpeg'}
    SUPPORTED_PDF_FORMATS = {'.pdf'}
    logger = logging.getLogger(__name__)

    def __init__(self):
        super().__init__()

        self.setWindowTitle('PDF OCR Demo')
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

        # Signals for OCR processing
        self.ocr_worker = OcrGui()
        self.ocr_worker.ocr_progress.connect(self.update_progress_bar)
        self.ocr_worker.ocr_completed.connect(self.on_ocr_completed)
        self.ocr_worker.ocr_error.connect(self.show_error_message)

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
        prev_action.triggered.connect(self.graphics_view.previous_page)
        view_menu.addAction(prev_action)

        next_action = QAction('Next Page', self)
        next_action.setShortcut('Ctrl+Right')
        next_action.triggered.connect(self.graphics_view.next_page)
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

        # Initialize OCR
        self.init_ocr_action = QAction('Initialize OCR', self)
        self.init_ocr_action.triggered.connect(self.initialize_ocr_engines)
        tool_bar.addAction(self.init_ocr_action)

        # Detect Tables Action
        self.detect_tables_action = QAction('Detect Tables', self)
        self.detect_tables_action.triggered.connect(self.detect_tables)
        self.detect_tables_action.setEnabled(False)
        tool_bar.addAction(self.detect_tables_action)

        # Run OCR
        self.run_ocr_action = QAction('Run OCR', self)
        self.run_ocr_action.triggered.connect(self.run_ocr)
        tool_bar.addAction(self.run_ocr_action)

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
        self.edit_mode_action.setEnabled(False)
        self.edit_mode_action.triggered.connect(self.toggle_edit_mode)
        tool_bar.addAction(self.edit_mode_action)

        # Manual Table Detection Action
        self.manual_table_detection_action = QAction("Manual Table Detection", self)
        self.manual_table_detection_action.setCheckable(True)
        self.manual_table_detection_action.triggered.connect(self.graphics_view.enable_manual_table_detection)
        tool_bar.addAction(self.manual_table_detection_action)

        # Add Vertical Line Action
        self.add_vertical_line_action = QAction('Add Vertical Line', self)
        self.add_vertical_line_action.setCheckable(True)
        self.add_vertical_line_action.triggered.connect(lambda checked: self.graphics_view.toggle_add_vertical_line_mode(checked))
        tool_bar.addAction(self.add_vertical_line_action)

        # Add Horizontal Line Action
        self.add_horizontal_line_action = QAction('Add Horizontal Line', self)
        self.add_horizontal_line_action.setCheckable(True)
        self.add_horizontal_line_action.triggered.connect(lambda checked: self.graphics_view.toggle_add_horizontal_line_mode(checked))
        tool_bar.addAction(self.add_horizontal_line_action)

        # Group the line actions to make them exclusive
        self.line_action_group = QActionGroup(self)
        self.line_action_group.addAction(self.add_vertical_line_action)
        self.line_action_group.addAction(self.add_horizontal_line_action)
        self.line_action_group.setExclusive(True)

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
        # Output Dock
        self.output_dock = QDockWidget('Output', self)
        self.output_dock.setAllowedAreas(Qt.BottomDockWidgetArea | Qt.TopDockWidgetArea)

        # Create a tab widget to hold the outputs
        self.output_tabs = QTabWidget()
        self.output_dock.setWidget(self.output_tabs)

        # Log Output
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.output_tabs.addTab(self.log_output, 'Log Output')

        # Table Widget to display tables
        self.tableWidget = QTableWidget()
        self.output_tabs.addTab(self.tableWidget, 'Table View')

        # CSV Output Preview
        self.csv_output = QTextEdit()
        self.csv_output.setReadOnly(True)
        self.output_tabs.addTab(self.csv_output, 'CSV Output')

        # Set default tab to Log Output
        self.output_tabs.setCurrentWidget(self.log_output)

        self.addDockWidget(Qt.BottomDockWidgetArea, self.output_dock) 
        self.output_dock.raise_()                

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
        self.progress_bar.setValue(tasks_completed)

    def set_table_detection_method(self, method_name):
        self.table_detection_method = method_name
        self.status_bar.showMessage(f'Table Detection Method set to: {method_name}', 5000)

    def update_recent_files_menu(self):
        self.recent_files_menu.clear()
        for file_path in self.recent_files:
            action = QAction(file_path, self)
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

            selected_text = current_item.text(0)  # Specify the column index

            # Determine if the selected item is a Page, Image, or Cropped image
            if selected_text.startswith("Page") or selected_text.startswith("Image"):
                # Extract page or image index
                index = int(selected_text.split(" ")[1]) - 1
                is_pdf = selected_text.startswith("Page")
                image_path = self.image_file_paths[index]
                self.perform_table_detection(image_path, page_index=index, is_pdf=is_pdf, cropped_index=None)

            elif selected_text.startswith("Cropped"):
                # Extract parent page index and cropped index
                parent_item = current_item.parent()
                if not parent_item:
                    self.show_error_message("Cropped item has no parent page.")
                    return

                parent_text = parent_item.text(0)
                page_index = int(parent_text.split(" ")[1]) - 1

                # Extract cropped index
                cropped_text = selected_text.split(":")[0]  # e.g., "Cropped 1"
                cropped_index = int(cropped_text.split(" ")[1]) - 1
                image_path = self.cropped_images[page_index][cropped_index]
                self.perform_table_detection(image_path, page_index=page_index, is_pdf=False, cropped_index=cropped_index)

            else:
                self.show_error_message("Invalid selection for table detection.")
                return

        except Exception as e:
            self.logger.error(f"Error in detect_tables: {e}", exc_info=True)
            self.show_error_message(f"An error occurred during table detection: {e}")

    def perform_table_detection(self, image_path, page_index, is_pdf=True, cropped_index=None):
        """Helper method to perform table detection on a single image."""
        try:
            if self.table_detection_method == 'Peaks and Troughs':
                horizontal_positions, vertical_positions, _ = ltd.find_table_peaks_troughs(
                    image_path,
                    horizontal_state="border",
                    vertical_state="border"
                )
            elif self.table_detection_method == 'Transitions':
                horizontal_positions, vertical_positions, _ = ltd.find_table_transitions(
                    image_path,
                    threshold=15,
                    min_distance=10,
                    smoothing_window=5
                )
            else:
                self.show_error_message('Invalid table detection method selected.')
                return

            # Convert positions to QLineF objects for drawing lines
            lines = []
            pil_image = Image.open(image_path)
            image_width, image_height = pil_image.size

            for y in horizontal_positions:
                line = QLineF(0, y, image_width, y)
                lines.append(line)
            for x in vertical_positions:
                line = QLineF(x, 0, x, image_height)
                lines.append(line)

            # Store lines
            if cropped_index is not None:
                key = f"{page_index}_{cropped_index}"
            else:
                key = f"{page_index}_full"
            self.lines[key] = lines

            # Display lines on the image in the preview with the correct key
            self.graphics_view.display_lines(lines, key=key)  # Pass the key here

            self.logger.info(f"Table detection completed for {'cropped image' if cropped_index is not None else 'page/image'} {page_index + 1}")

        except Exception as e:
            if cropped_index is not None:
                self.show_error_message(f'Table detection on cropped image failed: {e}')
                self.logger.error(f'Table detection on cropped image {cropped_index + 1} of page {page_index + 1} failed: {e}', exc_info=True)
            else:
                self.show_error_message(f'Table detection on {"page" if is_pdf else "image"} failed: {e}')
                self.logger.error(f'Table detection on {"page" if is_pdf else "image"} {page_index + 1} failed: {e}', exc_info=True)

    def open_pdf(self):
        options = QFileDialog.Options()
        file_name, _ = QFileDialog.getOpenFileName(self, "Open File", "", "PDF Files (*.pdf);;Image Files (*.png);;All Files (*)", options=options)
        if file_name:
            self.process_files([file_name])
            self.update_recent_files(file_name)

    def on_rectangle_selected(self, rect):
        """Handle the event when a rectangle is selected for cropping in the graphics view."""
        try:
            if self.current_page_index < 0 or self.current_page_index >= len(self.pil_images):
                raise IndexError("Current page index is out of bounds.")

            self.logger.info(f"Cropping area selected on page {self.current_page_index + 1}: {rect}")

            # Crop the selected area using the PIL image
            cropped_image = self.crop_image_pil(self.pil_images[self.current_page_index], rect)
            if cropped_image is None:
                raise ValueError("Cropping returned None.")

            # Save the cropped image
            cropped_image_path, page_index, cropped_index = self.save_cropped_image(cropped_image, rect)

            if cropped_image_path:
                # Emit the signal with necessary parameters
                self.croppedImageCreated.emit(page_index, cropped_index, cropped_image_path)

                # Optionally, refresh the project list to show the new cropped image
                self.populate_project_list()

                self.cropping_mode_action.setChecked(False)
                self.graphics_view.enable_cropping_mode(False)
                self.logger.info("Cropping mode turned off after cropping action.")

            return cropped_image_path, page_index, cropped_index

        except IndexError as e:
            self.logger.error(f"Index error in on_rectangle_selected: {e}")
            self.show_error_message(f"An error occurred: {e}")
            return None, None, None

        except Exception as e:
            self.logger.error(f"Error cropping image: {e}")
            self.show_error_message(f"Failed to crop image: {e}")
            return None, None, None

    def detect_line_intersections(self):
        """Detect intersections between vertical and horizontal lines and record them as table bounding boxes."""
        try:
            vertical_lines = [line for line in self.graphics_view._line_items if line.orientation == 'vertical']
            horizontal_lines = [line for line in self.graphics_view._line_items if line.orientation == 'horizontal']
            bounding_boxes = []

            for v_line in vertical_lines:
                v_x = v_line.line.p1().x()  # Access 'line' as an attribute, not a method
                for h_line in horizontal_lines:
                    h_y = h_line.line.p1().y()  # Access 'line' as an attribute, not a method
                    bounding_boxes.append(QRectF(v_x, h_y, 1, 1))  # Tiny rectangles at intersections

            self.bounding_boxes = bounding_boxes
            self.logger.info(f"Detected {len(bounding_boxes)} intersections.")
            self.status_bar.showMessage(f"Detected {len(bounding_boxes)} table intersections.", 5000)
        except Exception as e:
            self.logger.error(f"Error detecting intersections: {e}", exc_info=True)
            self.show_error_message(f"Failed to detect table intersections: {e}")

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
        """Handle the event when a line is modified in the PDFGraphicsView."""
        self.logger.info(f"Line modified on page {self.graphics_view.current_page_index + 1}")
        self.save_current_lines()
        self.detect_line_intersections()  # Detect intersections after modification

    def save_current_lines(self):
        """Save the current lines for the page."""
        lines = self.graphics_view.get_lines()
        self.lines[self.graphics_view.current_page_index] = lines
        self.logger.info(f"Lines saved for page {self.graphics_view.current_page_index + 1}")

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
            self.graphics_view.load_image(qimage)

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
        """Handle the movement of a line item."""
        try:
            # Capture the previous line position before the move
            previous_line = line_item.line  # Access the stored line

            # Create MoveLineAction
            action = MoveLineAction(self, line_item, previous_line, new_line)
            self.graphics_view.undo_stack.append(action)
            self.graphics_view.redo_stack.clear()
            self.graphics_view.lineModified.emit()
            self.logger.info(f"Line moved from {previous_line} to {new_line}")

            # Update the lines dictionary
            key = f"{self.graphics_view.current_page_index}_full"
            if key in self.lines:
                try:
                    self.lines[key].remove(previous_line)
                    self.lines[key].append(new_line)
                except ValueError:
                    self.logger.warning(f"Line {previous_line} not found in lines[{key}].")
        except AttributeError:
            self.logger.error(f"LineItem does not have 'line' attribute.", exc_info=True)
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
                    self.handle_pdf_file(path)
                
                # Handle supported image files
                elif ext in self.SUPPORTED_IMAGE_FORMATS:
                    self.handle_image_file(path)
                
                # Unsupported file type
                else:
                    self.show_error_message(f"Unsupported file type: {file_path}")
                    self.logger.error(f"Unsupported file type: {file_path}")

        except Exception as e:
            self.show_error_message(f"An error occurred while processing files: {e}")
            self.logger.error(f"Error in process_files: {e}", exc_info=True)

    def handle_image_file(self, path):
        """Handle loading of an image file."""
        self.clear_current_project()
        try:
            image = QImage(str(path))
            if image.isNull():
                raise ValueError("Failed to load image. File may be corrupted.")

            # Set project_folder to a dedicated directory for the project
            self.project_folder = os.path.join(os.path.dirname(os.path.abspath(path)), "OCR_Project")
            os.makedirs(self.project_folder, exist_ok=True)
            self.logger.info(f"Project folder set to: {self.project_folder}")

            # Convert QImage to PIL Image for consistency
            pil_image = Image.open(str(path)).convert('RGB')
            self.pil_images.append(pil_image)

            # Convert PIL Image to QImage
            qimage = self.pil_image_to_qimage(pil_image)
            self.qimages.append(qimage)

            # Save the image as an image file in the temporary directory
            temp_dir = Path('temp_images')
            temp_dir.mkdir(exist_ok=True)
            page_index = len(self.pil_images) - 1  # Zero-based index
            image_file_path = temp_dir / f"image_{page_index + 1}.png"
            pil_image.save(image_file_path, "PNG")
            self.image_file_paths.append(str(image_file_path))

            # Load the image into the graphics view
            self.graphics_view.load_image(qimage)

            # Populate the project list with the new image as a top-level item
            self.populate_project_list()

            # Display the newly added image
            self.current_page_index = len(self.pil_images) - 1
            self.show_current_page()
            self.status_bar.showMessage(f"Image '{path.name}' Loaded Successfully", 5000)

            # Enable actions once an image is loaded
            self.enable_actions_after_loading()

            self.update_recent_files(str(path))  # Update recent files

            self.logger.info(f"Image loaded and added to project: {path}")

        except Exception as e:
            self.show_error_message(f"Error loading image '{path.name}': {e}")
            self.logger.error(f"Error loading image from {path}: {e}", exc_info=True)

    def handle_pdf_file(self, path):
        """Handle loading of a PDF file."""
        try:
            self.status_bar.showMessage('Loading PDF...')
            self.logger.info(f"Loading PDF file: {path}")
            
            # Set project_folder to the directory containing the PDF
            self.project_folder = os.path.dirname(os.path.abspath(path))
            self.logger.info(f"Project folder set to: {self.project_folder}")
            
            # Convert PDF to list of PIL Images
            pil_images = convert_from_path(str(path))
            if not pil_images:
                raise ValueError('No pages found in the PDF.')

            for pil_img in pil_images:
                pil_img = pil_img.convert('RGB')  # Ensure consistency in image mode
                self.pil_images.append(pil_img)
                qimage = self.pil_image_to_qimage(pil_img)
                self.qimages.append(qimage)

            # Save each page as an image file
            temp_dir = Path('temp_images')
            temp_dir.mkdir(exist_ok=True)
            for idx, pil_img in enumerate(self.pil_images[-len(pil_images):], start=1):
                image_file_path = temp_dir / f"page_{idx}.png"
                pil_img.save(image_file_path, "PNG")
                self.image_file_paths.append(str(image_file_path))

            # Populate the project list with page names as top-level items
            self.populate_project_list()

            # Display the first page initially
            self.current_page_index = len(self.pil_images) - len(pil_images)
            self.show_current_page()
            self.status_bar.showMessage('PDF Loaded Successfully', 5000)

            # Enable actions once a PDF is loaded
            self.enable_actions_after_loading()

            self.logger.info(f"PDF loaded and converted to images: {path}")

        except Exception as e:
            self.logger.error(f'Failed to load PDF: {e}', exc_info=True)
            QMessageBox.critical(self, 'Error', f'Failed to load PDF: {e}')
            self.status_bar.showMessage('Failed to load PDF', 5000)

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
        """Load a PDF and convert each page into PIL and QImage formats."""
        self.status_bar.showMessage('Loading PDF...')
        QApplication.processEvents()

        try:
            # Convert PDF to list of PIL Images
            pil_images = convert_from_path(file_path)
            if not pil_images:
                raise ValueError('No pages found in the PDF.')
            
            self.pil_images = pil_images  # Store PIL Images
            
            # Convert PIL Images to QImages
            self.qimages = [self.pil_image_to_qimage(pil_img) for pil_img in pil_images]
            
            self.current_page_index = 0  # Start from the first page
            # self.load_image(self.qimages[self.current_page_index])  # Removed
            
            # Save each page as an image file
            temp_dir = Path('temp_images')
            temp_dir.mkdir(exist_ok=True)
            self.image_file_paths = []
            for idx, pil_img in enumerate(self.pil_images):
                image_file_path = temp_dir / f"page_{idx + 1}.png"
                pil_img.save(image_file_path, "PNG")
                self.image_file_paths.append(image_file_path)
            
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

    def update_page_label(self, page_index):
        """Update the page label or selection in the project list when the page changes."""
        try:
            self.project_list.setCurrentRow(page_index + 1)
        except Exception as e:
            self.logger.error(f"Error updating page label: {e}")

    def show_current_page(self):
        """Display the current page in the graphics view by loading it from disk."""
        try:
            # Check if the current page index is valid
            if not self.image_file_paths or self.current_page_index >= len(self.image_file_paths):
                self.logger.error(f'Invalid page index: {self.current_page_index}')
                return

            # Load the image for the current page from disk
            image_file_path = self.image_file_paths[self.current_page_index]
            pil_image = self.pil_images[self.current_page_index]
            qimage = self.pil_image_to_qimage(pil_image)  # Convert PIL Image to QImage
            self.graphics_view.load_image(qimage)  # Directly call PDFGraphicsView's load_image

            # Log the successful loading of the page
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

        except Exception as e:
            self.logger.error(f"Failed to display page {self.current_page_index}: {e}", exc_info=True)
            self.show_error_message(f"An error occurred while displaying page {self.current_page_index + 1}: {e}")

    def save_current_rectangles(self):
        rects = self.graphics_view.get_rectangles()
        self.rectangles[self.current_page_index] = rects
        self.logger.info(f"Rectangles saved for page {self.current_page_index + 1}")

    def save_cropped_image(self, cropped_image, crop_rect):
        """Save the cropped image to disk and update internal structures."""
        try:
            if not self.project_folder:
                # Prompt the user to select a project folder
                self.project_folder = QFileDialog.getExistingDirectory(self, "Select Project Folder")
                if not self.project_folder:
                    raise ValueError("Project folder not selected.")
                self.logger.info(f"Project folder set to: {self.project_folder}")

            cropped_image_path = os.path.join(
                self.project_folder,
                f"cropped_page_{self.current_page_index + 1}_{len(self.cropped_images.get(self.current_page_index, [])) + 1}.png"
            )

            # Ensure the cropped image directory exists
            os.makedirs(os.path.dirname(cropped_image_path), exist_ok=True)

            # Save the cropped image
            cropped_image.save(cropped_image_path)
            self.logger.info(f"Cropped image saved to {cropped_image_path}")

            # Add the cropped image to the cropped images dictionary under the current page
            if self.current_page_index not in self.cropped_images:
                self.cropped_images[self.current_page_index] = []
            self.cropped_images[self.current_page_index].append(cropped_image_path)

            # Determine the cropped index
            cropped_index = len(self.cropped_images[self.current_page_index])

            # Create a red rectangle on the preview
            rect_item = QGraphicsRectItem(crop_rect)
            rect_item.setPen(QPen(QColor(255, 0, 0), 2))  # Red pen
            self.graphics_view.scene().addItem(rect_item)

            # Emit the signal with cropped image details
            return cropped_image_path, self.current_page_index, cropped_index

        except Exception as e:
            self.logger.error(f"Error saving cropped image: {e}")
            self.show_error_message(f"Failed to save cropped image: {e}")
            return None, None, None

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
        self.status_bar.showMessage('Initializing OCR engines...')
        QApplication.processEvents()
        try:
            self.ocr_engine = rtr.initialize_paddleocr()
            self.easyocr_engine = rtr.initialize_easyocr()
            rtr.configure_logging()
            self.ocr_initialized = True
            self.status_bar.showMessage('OCR engines initialized', 5000)
        except Exception as e:
            self.show_error_message(f'Failed to initialize OCR engines: {e}')
            self.ocr_initialized = False

    def run_ocr(self):
        if not self.ocr_initialized:
            self.show_error_message('Please initialize the OCR engines before running OCR.')
            return
        if self.ocr_running:
            # Cancel OCR
            self.ocr_cancel_event.set()
            self.status_bar.showMessage('Cancelling OCR...', 5000)
            self.run_ocr_action.setText('Run OCR')
            self.ocr_running = False
        else:
            # Start OCR
            self.status_bar.showMessage('Running OCR...', 5000)
            QApplication.processEvents()
            self.save_current_rectangles()
            self.save_current_lines()
            self.progress_bar = QProgressBar()
            self.status_bar.addPermanentWidget(self.progress_bar)
            total_tasks = len(self.graphics_view.pdf_images)  # Calculate total tasks
            self.progress_bar.setMaximum(total_tasks)
            self.progress_bar.setValue(0)
            self.ocr_cancel_event = threading.Event()
            self.run_ocr_action.setText('Cancel OCR')
            self.ocr_running = True

            # Prepare paths
            storedir = os.path.abspath("temp_gui")
            os.makedirs(storedir, exist_ok=True)
            pdf_file = self.current_pdf_path
            output_csv = os.path.join(self.project_folder, "ocr_results.csv")

            # Start the OCRWorker thread
            self.ocr_worker = OCRWorker(pdf_file, storedir, output_csv, self.ocr_cancel_event)
            self.ocr_worker.ocr_progress.connect(self.on_ocr_progress)
            self.ocr_worker.ocr_completed.connect(self.on_ocr_completed)
            self.ocr_worker.ocr_error.connect(self.on_ocr_error)
            self.ocr_worker.start()

    def ocr_task(self):
        """Runs the OCR task when triggered by the GUI."""
        try:
            # Prepare the necessary paths
            storedir = os.path.join("\\\\?\\", os.path.abspath("temp_gui"))  # Use absolute path with \\?\ prefix
            os.makedirs(storedir, exist_ok=True)

            # Get the PDF file path and output CSV path from the GUI context
            pdf_file = self.current_pdf_path
            output_csv = os.path.join(self.project_folder, "ocr_results.csv")

            # Run the OCR pipeline and get the results
            all_table_data, total, bad, easyocr_count, paddleocr_count, processing_time = run_ocr_pipeline(pdf_file, storedir, output_csv)

            # Handle post-OCR processing in the GUI
            self.ocr_completed.emit((all_table_data, processing_time))  # Emit completion signal with results

            num_pages = len(self.graphics_view.pdf_images)
            avg_time = processing_time / num_pages if num_pages else 0
            self.status_bar.showMessage(f'OCR Completed. Average time per page: {avg_time:.2f} seconds', 5000)

        except Exception as e:
            self.logger.error(f"Critical error in OCR task: {e}")
            self.ocr_error.emit(f"Critical error: {e}")  # Emit error signal
        finally:
            self.ocr_running = False
            self.ocr_progress.emit(1, 1)  # Ensure progress is complete
            self.run_ocr_action.setText('Run OCR')
    
    def crop_image_pil(self, pil_image, rect):
        """
        Crop the selected area from the PIL image based on the QRectF provided.

        Args:
            pil_image (PIL.Image.Image): The original PIL image.
            rect (QRectF): The cropping rectangle in scene coordinates.

        Returns:
            PIL.Image.Image: The cropped image.
        """
        try:
            pixmap_item = self.graphics_view._pixmap_item
            if not pixmap_item:
                self.logger.error("No pixmap item found in graphics view.")
                raise ValueError("No image loaded in the graphics view.")

            # Map the rect from scene coordinates to pixmap (item) coordinates
            mapped_rect = pixmap_item.mapFromScene(rect).boundingRect()

            # Get the pixmap's width and height
            pixmap_width = pixmap_item.pixmap().width()
            pixmap_height = pixmap_item.pixmap().height()

            # Get the PIL image's width and height
            image_width, image_height = pil_image.size

            # Calculate scale factors between pixmap and image
            scale_x = image_width / pixmap_width
            scale_y = image_height / pixmap_height

            # To maintain aspect ratio and prevent skewing, use the same scale factor
            scale = min(scale_x, scale_y)

            # Apply scale factor to the mapped rect to get pixel coordinates
            left = int(max(0, mapped_rect.left() * scale))
            top = int(max(0, mapped_rect.top() * scale))
            right = int(min(mapped_rect.right() * scale, image_width))
            bottom = int(min(mapped_rect.bottom() * scale, image_height))

            # Log the calculated crop coordinates
            self.logger.debug(f"Cropping rectangle (pixels): Left={left}, Top={top}, Right={right}, Bottom={bottom}")

            # Ensure the crop box is valid (right > left and bottom > top)
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
        else:
            self.graphics_view.setDragMode(QGraphicsView.NoDrag)

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

    def display_table(self, all_table_data):
        self.tableWidget.clear()
        self.tableWidget.setRowCount(0)
        self.tableWidget.setColumnCount(0)
        if all_table_data:
            # For simplicity, display data from the first page
            page_index = sorted(all_table_data.keys())[0]
            table_data = all_table_data[page_index]
            if table_data:
                max_row = max(table_data.keys())
                max_col = max(max(cols.keys()) for cols in table_data.values())
                self.tableWidget.setRowCount(max_row + 1)
                self.tableWidget.setColumnCount(max_col + 1)
                for row_index, cols in table_data.items():
                    for col_index, value in cols.items():
                        item = QTableWidgetItem(value)
                        item.setFlags(item.flags() | Qt.ItemIsEditable)  # Make cell editable
                        self.tableWidget.setItem(row_index, col_index, item)

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
        # Unpack the result
        all_table_data, total, bad, easyocr_count, paddleocr_count, processing_time = result

        # Determine where to save the CSV
        if self.current_pdf_path:
            default_csv_name = os.path.splitext(os.path.basename(self.current_pdf_path))[0] + '.csv'
            default_csv_path = os.path.join(self.project_folder, default_csv_name)
        else:
            default_csv_path = os.path.join(self.project_folder, 'ocr_results.csv')

        csv_file_path = default_csv_path  # Save CSV directly into the project folder

        # Write the table data to CSV
        try:
            rtr.write_to_csv(all_table_data, csv_file_path)
        except Exception as e:
            self.show_error_message(f"Failed to write CSV file: {e}")
            self.logger.error(f"Failed to write CSV file: {e}")
            return

        # Read the CSV content and display it in the GUI's CSV output panel
        try:
            with open(csv_file_path, 'r', encoding='utf-8') as f:
                csv_content = f.read()
                self.csv_output.setPlainText(csv_content)
        except Exception as e:
            self.show_error_message(f"Failed to read CSV file: {e}")
            self.logger.error(f"Failed to read CSV file: {e}")

        self.status_bar.showMessage(f"OCR Completed. Results saved to {csv_file_path}", 5000)
        self.last_csv_path = csv_file_path  # Store the path of the last saved CSV for later use
        self.export_excel_action.setEnabled(True)  # Enable the "Export to Excel" action

        # Display the OCR results in the table view
        self.display_table(all_table_data)

        # Cleanup temporary files used during OCR
        rtr.cleanup('temp_gui')

        # Remove the progress bar from the status bar
        if self.progress_bar:
            self.status_bar.removeWidget(self.progress_bar)
            self.progress_bar = None

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

        # Optional: Display detected language (assuming this functionality is in place)
        detected_language = 'English'  # Placeholder - Replace with actual detected language if available
        self.status_bar.showMessage(f'Detected Language: {detected_language}', 5000)

        # Reset the OCR running state and button text
        self.ocr_running = False
        self.run_ocr_action.setText('Run OCR')
        self.save_csv_action.setEnabled(True)

    def on_ocr_progress(self, tasks_completed, total_tasks):
        self.progress_bar.setValue(tasks_completed)
        self.status_bar.showMessage(f'Processing OCR... ({tasks_completed}/{total_tasks})', 5000)

    def on_ocr_error(self, error_message):
        """
        Handles errors that occur during the OCR process.
        """
        # Update status bar to reflect OCR failure
        self.status_bar.showMessage('OCR Failed', 5000)

        # Show an error message dialog
        self.show_error_message(f'OCR Failed: {error_message}')

        # Remove the progress bar from the status bar
        if self.progress_bar:
            self.status_bar.removeWidget(self.progress_bar)
            self.progress_bar = None

        # Reset the OCR running state and button text
        self.ocr_running = False
        self.run_ocr_action.setText('Run OCR')

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

    def update_project_list(self, page_index, cropped_index, cropped_image_path):
        """Update the project list with the new cropped image."""
        try:
            self.logger.info(f"update_project_list called with page_index={page_index}, cropped_index={cropped_index}, image_path={cropped_image_path}")

            if page_index is None or cropped_index is None or cropped_image_path is None:
                self.logger.warning("Invalid data received for updating project list.")
                return

            parent_item = self.project_list.topLevelItem(page_index)
            if parent_item:
                cropped_item_text = f"Cropped {cropped_index}: {os.path.basename(cropped_image_path)}"
                cropped_item = QTreeWidgetItem(parent_item)
                cropped_item.setText(0, cropped_item_text)
                cropped_item.setFlags(cropped_item.flags() | Qt.ItemIsSelectable | Qt.ItemIsEnabled)
                parent_item.addChild(cropped_item)
                parent_item.setExpanded(True)  # Expand to show the new child
                self.logger.info(f"Added cropped image to project list: {cropped_image_path}")

                # Optionally, scroll to the new item
                self.project_list.scrollToItem(cropped_item)
            else:
                self.logger.warning(f"Parent page item not found in project list for page index {page_index}")

        except Exception as e:
            self.logger.error(f"Error updating project list: {e}", exc_info=True)
            self.show_error_message(f"Failed to update project list: {e}")

    def update_project_explorer(self):
        """Refresh the project explorer to reflect current project folder contents."""
        try:
            self.project_list.clear()
            if self.project_folder:
                # Add the project folder as a top-level item
                project_item = QTreeWidgetItem(self.project_list)
                project_item.setText(0, os.path.basename(self.project_folder))
                project_item.setFlags(project_item.flags() | Qt.ItemIsSelectable | Qt.ItemIsEnabled)

                # Add pages and their cropped images
                for page_index, image_path in enumerate(self.image_file_paths):
                    page_item = QTreeWidgetItem(project_item)
                    page_item.setText(0, f"Page {page_index + 1}")
                    page_item.setFlags(page_item.flags() | Qt.ItemIsSelectable | Qt.ItemIsEnabled)

                    # Add cropped images under the page
                    if page_index in self.cropped_images:
                        for cropped_index, cropped_image_path in enumerate(self.cropped_images[page_index]):
                            cropped_item = QTreeWidgetItem(page_item)
                            cropped_item.setText(0, f"Cropped {cropped_index + 1}: {os.path.basename(cropped_image_path)}")
                            cropped_item.setFlags(cropped_item.flags() | Qt.ItemIsSelectable | Qt.ItemIsEnabled)

                project_item.setExpanded(True)  # Expand the project folder to show pages and cropped images

        except Exception as e:
            self.logger.error(f"Error updating project explorer: {e}", exc_info=True)
            self.show_error_message(f"Failed to update project explorer: {e}")

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
    # Configure logging at the very start
    configure_logging()
    logger = logging.getLogger(__name__)
    logger.info("Application started.")

    # Set up the global exception hook
    sys.excepthook = exception_hook

    # Initialize the QApplication
    app = QApplication(sys.argv)

    # Attempt to apply the stylesheet
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

    # Initialize and show the main window
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

    # Execute the application and handle unexpected exceptions during runtime
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
