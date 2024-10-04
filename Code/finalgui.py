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
import shutil
import csv
import traceback
import pickle
from email.message import EmailMessage

# Third-party imports
import cv2
import numpy as np
import pandas as pd
import webbrowser
import urllib.parse
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QAction, QFileDialog, QGraphicsView, QGraphicsScene,
    QGraphicsRectItem, QGraphicsLineItem, QVBoxLayout, QHBoxLayout, QWidget, QSplitter, QTextEdit,
    QMenuBar, QMenu, QToolBar, QLabel, QComboBox, QProgressBar, QStatusBar,
    QPushButton, QMessageBox, QGraphicsPixmapItem, QTableWidget, QTableWidgetItem,
    QDockWidget, QListWidget, QTabWidget, QInputDialog, QWidgetAction, QActionGroup, QTextBrowser, QLineEdit
)
from PyQt5.QtGui import QPixmap, QImage, QPen, QColor, QPainter, QFont, QDragEnterEvent, QDropEvent
from PyQt5.QtCore import Qt, QRectF, QObject, pyqtSignal, QLineF, QThread
from pdf2image import convert_from_path
from PIL import Image
from logging.handlers import RotatingFileHandler

# Local imports
from ocr_pipe import run_ocr_pipeline
import ocr_pipe as rtr
import luminosity_table_detection as ltd

# Manual table detection imports
from tkinter import Tk
from table_detection_manual import TableDividerApp  # Assuming your table detection code is in a separate file

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
    logger.addHandler(console_handler)

class EmittingStream(QObject):
    textWritten = pyqtSignal(str)

    def write(self, text):
        text = text.strip()
        if text:
            self.textWritten.emit(str(text + '\n'))

    def flush(self):
        pass

class LineItem(QGraphicsLineItem):
    def __init__(self, line, parent=None):
        super().__init__(line)
        self.setFlags(
            QGraphicsLineItem.ItemIsSelectable |
            QGraphicsLineItem.ItemIsMovable |
            QGraphicsLineItem.ItemSendsGeometryChanges
        )
        self.setPen(QPen(QColor(0, 255, 0), 1))

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        # Emit signal to notify that the line has been modified
        self.scene().views()[0].lineModified.emit()

class PDFGraphicsView(QGraphicsView):
    rectangleSelected = pyqtSignal(QRectF)
    lineModified = pyqtSignal()
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

        # Connect signals
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

    def pil_image_to_qimage(self, pil_image):
        """Convert PIL Image to QImage."""
        try:
            if pil_image.mode == "RGB":
                r, g, b = pil_image.split()
                pil_image = Image.merge("RGB", (r, g, b))
            elif pil_image.mode == "RGBA":
                r, g, b, a = pil_image.split()
                pil_image = Image.merge("RGBA", (r, g, b, a))
            elif pil_image.mode == "L":
                pil_image = pil_image.convert("RGBA")
            else:
                pil_image = pil_image.convert("RGBA")
            data = pil_image.tobytes("raw", pil_image.mode)
            qimage = QImage(data, pil_image.width, pil_image.height, QImage.Format_RGBA8888)
            return qimage
        except Exception as e:
            self.logger.error(f"Error converting PIL image to QImage: {e}")
            self.get_main_window().show_error_message(f"An error occurred while converting image: {e}")
            return QImage()

    def load_pdf(self, file_path):
        """Load a PDF and convert each page into a QImage."""
        try:
            pil_images = convert_from_path(file_path)  # Convert PDF to list of PIL Images
            # Convert PIL Images to QImages
            self.pdf_images = [self.pil_image_to_qimage(pil_img) for pil_img in pil_images]
            self.current_page_index = 0  # Start from the first page
            self.load_image(self.pdf_images[self.current_page_index])  # Load the first page
        except Exception as e:
            self.get_main_window().show_error_message(f"Error loading PDF: {e}")
            self.logger.error(f"Error loading PDF: {e}")

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

    def load_image(self, image):
        """Load a QImage into the scene."""
        try:
            self.scene().clear()
            qt_image = QPixmap.fromImage(image)
            self._pixmap_item = QGraphicsPixmapItem(qt_image)
            self.scene().addItem(self._pixmap_item)
            self.fitInView(self._pixmap_item, Qt.KeepAspectRatio)
            self._rect_items.clear()
            self._line_items.clear()
        except Exception as e:
            self.logger.error(f"Error loading image into scene: {e}")
            self.get_main_window().show_error_message(f"An error occurred while loading image: {e}")

    def mousePressEvent(self, event):
        try:
            if event.button() == Qt.LeftButton:
                main_window = self.get_main_window()  # Get the OCRApp instance
                if main_window.cropping_mode_action.isChecked():
                    self._start_pos = self.mapToScene(event.pos())
                    self._current_rect_item = QGraphicsRectItem(QRectF(self._start_pos, self._start_pos))
                    pen = QPen(QColor(255, 0, 0), 2)
                    self._current_rect_item.setPen(pen)
                    self.scene().addItem(self._current_rect_item)
                else:
                    super().mousePressEvent(event)
            else:
                super().mousePressEvent(event)
        except Exception as e:
            self.logger.error(f"Error in mousePressEvent: {e}")
            self.get_main_window().show_error_message(f"An error occurred: {e}")
    
        def mouseMoveEvent(self, event):
            try:
                if self._current_rect_item:
                    rect = QRectF(self._start_pos, self.mapToScene(event.pos())).normalized()
                    self._current_rect_item.setRect(rect)
                else:
                    super().mouseMoveEvent(event)
            except Exception as e:
                self.logger.error(f"Error in mouseMoveEvent: {e}")
                self.get_main_window().show_error_message(f"An error occurred: {e}")

    def mouseReleaseEvent(self, event):
        try:
            if event.button() == Qt.LeftButton and self._current_rect_item:
                self._rect_items.append(self._current_rect_item)
                self.rectangleSelected.emit(self._current_rect_item.rect())
                self._current_rect_item = None
                # Save the rectangle as a cropped area if in cropping mode
                if self.cropping_mode:
                    rect = self._rect_items[-1].rect()  # Use the most recent rectangle
                    self.cropped_areas.append(rect)
            else:
                super().mouseReleaseEvent(event)
        except Exception as e:
            self.logger.error(f"Error in mouseReleaseEvent: {e}")
            self.get_main_window().show_error_message(f"An error occurred: {e}")

    def get_cropped_areas(self):
        """ Returns the list of cropped areas """
        return self.cropped_areas
    
    def keyPressEvent(self, event):
        try:
            if event.key() == Qt.Key_Delete:
                selected_items = self.scene().selectedItems()
                for item in selected_items:
                    if isinstance(item, QGraphicsRectItem):
                        self.scene().removeItem(item)
                        self._rect_items.remove(item)
                        # Record the action for undo/redo
                        action = RemoveRectangleAction(self, item)
                        self.undo_stack.append(action)
                        self.redo_stack.clear()  # Clear redo stack on new action
                    elif isinstance(item, QGraphicsLineItem):
                        self.scene().removeItem(item)
                        self._line_items.remove(item)
                        # Record the action for undo/redo
                        action = RemoveLineAction(self, item)
                        self.undo_stack.append(action)
                        self.redo_stack.clear()  # Clear redo stack on new action
                        self.lineModified.emit()
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
        try:
            if self.undo_stack:
                action = self.undo_stack.pop()
                action.undo()
                self.redo_stack.append(action)
        except Exception as e:
            self.logger.error(f"Error in undo_last_action: {e}")
            self.get_main_window().show_error_message(f"An error occurred: {e}")

    def redo_last_action(self):
        try:
            if self.redo_stack:
                action = self.redo_stack.pop()
                action.redo()
                self.undo_stack.append(action)
        except Exception as e:
            self.logger.error(f"Error in redo_last_action: {e}")
            self.get_main_window().show_error_message(f"An error occurred: {e}")

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

    def display_lines(self, lines):
        for line_item in self._line_items:
            self.scene().removeItem(line_item)
        self._line_items.clear()

        for line in lines:
            line_item = QGraphicsLineItem(line)
            self.scene().addItem(line_item)
            self._line_items.append(line_item)

    def get_lines(self):
        return [item.line() for item in self._line_items]

    def clear_lines(self):
        """Clear all the lines from the scene."""
        for line_item in self._line_items:
            self.scene().removeItem(line_item)
        self._line_items.clear()

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        try:
            if event.mimeData().hasUrls():
                urls = event.mimeData().urls()
                for url in urls:
                    if url.isLocalFile():
                        file_path = url.toLocalFile()
                        mime_type, _ = mimetypes.guess_type(file_path)
                        if mime_type == 'application/pdf':
                            self.load_pdf(file_path)  # Load the PDF if it's valid
                        elif mime_type in ['image/png', 'image/jpeg', 'image/jpg']:
                            image = QImage(file_path)
                            if image.isNull():
                                self.get_main_window().show_error_message(f"Failed to load image: {file_path}")
                                self.logger.error(f"Failed to load image: {file_path}")
                            else:
                                self.load_image(image)
                        else:
                            self.get_main_window().show_error_message("Invalid file type. Only PDF or image files supported.")
            else:
                self.get_main_window().show_error_message("Invalid file(s). Please drop local files only.")
        except Exception as e:
            self.get_main_window().show_error_message(f"An error occurred while dropping files: {e}")
            self.logger.error(f"Error in dropEvent: {e}")


class Action:
    """Base class for actions that can be undone/redone."""
    def undo(self):
        pass

    def redo(self):
        pass

class AddLineAction(Action):
    def __init__(self, view, line_item):
        self.view = view
        self.line_item = line_item

    def undo(self):
        self.view.scene().removeItem(self.line_item)
        self.view._line_items.remove(self.line_item)
        self.view.lineModified.emit()

    def redo(self):
        self.view.scene().addItem(self.line_item)
        self.view._line_items.append(self.line_item)
        self.view.lineModified.emit()

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

class RemoveLineAction(Action):
    def __init__(self, view, line_item):
        self.view = view
        self.line_item = line_item

    def undo(self):
        self.view.scene().addItem(self.line_item)
        self.view._line_items.append(self.line_item)
        self.view.lineModified.emit()

    def redo(self):
        self.view.scene().removeItem(self.line_item)
        self.view._line_items.remove(self.line_item)
        self.view.lineModified.emit()

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

class OcrGui(QObject):
    ocr_progress = pyqtSignal(int, int)
    ocr_completed = pyqtSignal(tuple)
    ocr_error = pyqtSignal(str)


# OCRWorker for running OCR in a separate thread
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

class OCRApp(QMainWindow):
    ocr_completed = pyqtSignal(object)
    ocr_progress = pyqtSignal(int, int)
    ocr_error = pyqtSignal(str)
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
        self.manual_table_app = None  # For manual table detection using Tkinter

        self.init_ui()
        self.last_csv_path = None  # Store the path of the last saved CSV
        self.project_folder = None  # Store the project folder path

        # Signals for OCR processing
        self.ocr_worker = OcrGui()
        self.ocr_worker.ocr_progress.connect(self.update_progress_bar)
        self.ocr_worker.ocr_completed.connect(self.on_ocr_completed)
        self.ocr_worker.ocr_error.connect(self.show_error_message)

    def init_ui(self):
        splitter = QSplitter(Qt.Horizontal)
        self.graphics_view = PDFGraphicsView(self)
        splitter.addWidget(self.graphics_view)

        self.project_list = QListWidget()
        splitter.addWidget(self.project_list)
        self.project_list.currentRowChanged.connect(self.change_page)

        splitter.setSizes([1900, 200])

        self.setCentralWidget(splitter)

        self.init_menu_bar()

        self.init_output_dock()

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

    def init_menu_bar(self):
        menu_bar = self.menuBar()
        # File Menu
        file_menu = menu_bar.addMenu('File')

        open_action = QAction('Open', self)
        open_action.setShortcut('Ctrl+O')
        open_action.triggered.connect(self.open_pdf)
        file_menu.addAction(open_action)

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

    def open_pdf(self):
        options = QFileDialog.Options()
        file_name, _ = QFileDialog.getOpenFileName(self, "Open File", "", "PDF Files (*.pdf);;Image Files (*.png);;All Files (*)", options=options)
        if file_name:
            self.process_files([file_name])

    def process_files(self, file_paths):
        """Process files that are dropped or opened and load them into the project."""
        try:
            for file_path in file_paths:
                if not os.path.exists(file_path):
                    self.show_error_message(f"File not found: {file_path}")
                    self.logger.error(f"File not found: {file_path}")
                    continue

                if file_path not in self.recent_files:
                    self.recent_files.insert(0, file_path)
                    if len(self.recent_files) > 5:
                        self.recent_files = self.recent_files[:5]
                        self.update_recent_files_menu()
                # Handle PDF files
                if file_path.lower().endswith('.pdf'):
                    self.current_pdf_path = file_path
                    # Create a folder for the PDF project
                    pdf_name = os.path.splitext(os.path.basename(file_path))[0]
                    self.project_folder = os.path.join(os.getcwd(), pdf_name)

                    try:
                        os.makedirs(self.project_folder, exist_ok=True)
                        self.load_pdf(file_path)
                    except OSError as e:
                        self.show_error_message(f"Error creating project folder: {e}")
                        self.logger.error(f"Error creating project folder: {e}")
                        return  # Stop further processing if project folder creation fails
                    
                # Handle PNG files
                elif file_path.lower().endswith('.png'):
                    try:
                        image = QImage(file_path)
                        if image.isNull():
                            raise ValueError("Failed to load image. File may be corrupted.")
                        self.load_image(image)
                    except Exception as e:
                        self.show_error_message(f"Error loading image: {e}")
                        self.logger.error(f"Error loading image from {file_path}: {e}")
                
                # Unsupported file type
                else:
                    self.show_error_message(f"Unsupported file type: {file_path}")
                    self.logger.error(f"Unsupported file type: {file_path}")

        except Exception as e:
            self.show_error_message(f"An error occurred while processing files: {e}")
            self.logger.error(f"Error in process_files: {e}")

    def load_pdf(self, file_path):
        """Load the PDF and convert each page to an image, saving them to disk."""
        self.status_bar.showMessage('Loading PDF...')
        QApplication.processEvents()

        try:
            # Create a temporary directory to store images
            temp_dir = Path('temp_images')
            if not temp_dir.exists():
                temp_dir.mkdir()

            # Convert PDF to images and save each page as a separate image file
            self.logger.info(f'Attempting to load PDF: {file_path}')
            self.pdf_images = convert_from_path(file_path, dpi=200)  # Lower DPI to manage memory usage
            total_pages = len(self.pdf_images)
            self.logger.info(f'Total pages in the PDF: {total_pages}')

            if total_pages == 0:
                raise ValueError('No pages found in the PDF.')

            # Save each page as an image file
            self.image_file_paths = []
            for idx, image in enumerate(self.pdf_images):
                image_file_path = temp_dir / f"page_{idx + 1}.png"
                image.save(image_file_path, "PNG")
                self.image_file_paths.append(image_file_path)

            self.current_page_index = 0
            self.rectangles = {}  # Reset rectangles
            self.lines = {}       # Reset lines

            # Populate the project list with page names
            self.project_list.clear()
            pdf_name = os.path.basename(file_path)
            self.project_list.addItem(f"{pdf_name}")
            for idx in range(total_pages):
                self.project_list.addItem(f"  - Page {idx + 1}")

            # Display the first page initially
            self.show_current_page()
            self.status_bar.showMessage('PDF Loaded Successfully', 5000)

        except Exception as e:
            self.logger.error(f'Failed to load PDF: {e}', exc_info=True)
            QMessageBox.critical(self, 'Error', f'Failed to load PDF: {e}')
            self.status_bar.showMessage('Failed to load PDF', 5000)

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
            total_tasks = len(self.pdf_images)  # Calculate total tasks
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

    def on_ocr_completed(self, result):
        all_table_data, processing_time = result
        self.status_bar.showMessage(f"OCR completed in {processing_time:.2f} seconds", 5000)
        self.display_table(all_table_data)

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
    
    def on_ocr_error(self, error_message):
        """Handles errors that occur during the OCR process."""
        self.status_bar.showMessage(f'OCR Failed: {error_message}', 5000)
        QMessageBox.critical(self, "OCR Error", f"An error occurred during OCR:\n{error_message}")
        if self.progress_bar:
            self.status_bar.removeWidget(self.progress_bar)
            self.progress_bar = None

    def start_manual_table_detection(self):
        """Open the manual table detection tool."""
        self.hide()  # Hide the main PyQt window
        root = Tk()  # Start Tkinter root
        self.manual_table_app = TableDividerApp(root, self.pdf_images)  # Pass images to the manual detection tool
        root.mainloop()  # Run the Tkinter event loop
        self.show()  # Show the main window after manual table detection

    def update_progress_bar(self, tasks_completed, total_tasks):
        self.progress_bar.setValue(tasks_completed)

    def on_rectangle_selected(self, rect):
        """Handle the event when a rectangle is selected for cropping in the graphics view."""
        self.logger.info(f"Cropping area selected on page {self.current_page_index + 1}: {rect}")
        
        # Clear any previously selected rectangle (limit to one rectangle)
        self.graphics_view.clear_rectangles()
        
        # Save the current rectangle selection
        self.rectangles[self.current_page_index] = [rect]

        # Crop the selected area
        try:
            cropped_image = self.crop_image_pil(self.pdf_images[self.current_page_index], rect)
            cropped_image_path = os.path.join(self.project_folder, f"cropped_page_{self.current_page_index + 1}.png")
            
            cropped_image.save(cropped_image_path)
            self.logger.info(f"Cropped image saved to {cropped_image_path}")

            self.preview_cropped_image(cropped_image)

            self.status_bar.showMessage(f"Cropped image saved as {cropped_image_path}", 5000)
        
        except Exception as e:
            self.logger.error(f"Error cropping image: {e}")
            self.show_error_message(f"Failed to crop image: {e}")

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

    def save_current_lines(self):
        """Save the current lines for the page."""
        lines = self.graphics_view.get_lines()
        self.lines[self.graphics_view.current_page_index] = lines
        self.logger.info(f"Lines saved for page {self.graphics_view.current_page_index + 1}")

    def change_page(self, current_page):
        """Handle page changes when a different page is selected from the project list."""
        if current_page < 0 or current_page >= len(self.pdf_images):
            return

        self.current_page_index = current_page
        self.show_current_page()
        self.graphics_view.clear_rectangles()
        self.graphics_view.clear_lines()
        page_rects = self.rectangles.get(self.current_page_index, [])
        page_lines = self.lines.get(self.current_page_index, [])

        for rect in page_rects:
            rect_item = QGraphicsRectItem(rect)
            pen = QPen(QColor(255, 0, 0), 2)
            rect_item.setPen(pen)
            self.graphics_view.scene().addItem(rect_item)
            self.graphics_view._rect_items.append(rect_item)

        self.graphics_view.display_lines(page_lines)

    def save_as(self):
        """Save the processed tables as a CSV."""
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

    def save_project(self):
        options = QFileDialog.Options()
        save_path, _ = QFileDialog.getSaveFileName(self, "Save Project As", "", "Project Files (*.proj);;All Files (*)", options=options)
        if save_path:
            project_data = {
                'current_pdf_path': self.current_pdf_path,
                'rectangles': self.rectangles,
                'lines': self.lines,
                'current_page_index': self.current_page_index,
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
        if pil_image.mode == 'RGB':
            data = pil_image.tobytes('raw', 'RGB')
            qimage = QImage(data, pil_image.width, pil_image.height, QImage.Format_RGB888)
        elif pil_image.mode == 'RGBA':
            data = pil_image.tobytes('raw', 'RGBA')
            qimage = QImage(data, pil_image.width, pil_image.height, QImage.Format_RGBA8888)
        else:
            pil_image = pil_image.convert('RGB')
            data = pil_image.tobytes('raw', 'RGB')
            qimage = QImage(data, pil_image.width, pil_image.height, QImage.Format_RGB888)
        return qimage

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

    def show_error_message(self, message, detailed_message=None, title="Error", icon=QMessageBox.Critical):
        """Display an enhanced error message with optional details."""
        error_dialog = QMessageBox(self)
        error_dialog.setWindowTitle(title)
        error_dialog.setIcon(icon)
        error_dialog.setText(message)
        
        if detailed_message:
            error_dialog.setDetailedText(detailed_message)
        
        error_dialog.setStandardButtons(QMessageBox.Ok)
        error_dialog.setStyleSheet("QLabel{min-width: 250px; font-size: 24px;}")
        
        error_dialog.exec_()

        self.logger.error(f"Error displayed: {message}")
        if detailed_message:
            self.logger.error(f"Details: {detailed_message}")

    def run_ocr(self):
        if not self.ocr_initialized:
            self.show_error_message('Please initialize the OCR engines before running OCR.')
            return
        if self.ocr_running:
            self.ocr_cancel_event.set()
            self.status_bar.showMessage('Cancelling OCR...', 5000)
            self.run_ocr_action.setText('Run OCR')
            self.ocr_running = False
        else:
            self.status_bar.showMessage('Running OCR...', 5000)
            QApplication.processEvents()
            self.save_current_rectangles()
            self.save_current_lines()
            self.progress_bar = QProgressBar()
            self.status_bar.addPermanentWidget(self.progress_bar)
            total_tasks = len(self.pdf_images)
            self.progress_bar.setMaximum(total_tasks)
            self.progress_bar.setValue(0)
            self.ocr_cancel_event = threading.Event()
            self.run_ocr_action.setText('Cancel OCR')
            self.ocr_running = True

            storedir = os.path.abspath("temp_gui")
            os.makedirs(storedir, exist_ok=True)
            pdf_file = self.current_pdf_path
            output_csv = os.path.join(self.project_folder, "ocr_results.csv")

            self.ocr_worker = OCRWorker(pdf_file, storedir, output_csv, self.ocr_cancel_event)
            self.ocr_worker.ocr_progress.connect(self.on_ocr_progress)
            self.ocr_worker.ocr_completed.connect(self.on_ocr_completed)
            self.ocr_worker.ocr_error.connect(self.on_ocr_error)
            self.ocr_worker.start()


def main():
    configure_logging()
    app = QApplication(sys.argv)
    window = OCRApp()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()


