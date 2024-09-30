# Standard library imports
import sys
import os
from pathlib import Path
import logging
import mimetypes
import threading
import time
import signal
import smtplib
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
    QDockWidget, QListWidget, QTabWidget, QInputDialog, QWidgetAction, QActionGroup
)
from PyQt5.QtGui import QPixmap, QImage, QPen, QColor, QPainter, QFont
from PyQt5.QtCore import Qt, QRectF, QObject, pyqtSignal, QLineF
from PyQt5.QtGui import QDragEnterEvent, QDropEvent
from pdf2image import convert_from_path
from PIL import Image


# Local imports
from RunThroughRefactor_1 import run_ocr_pipeline
import RunThroughRefactor_1 as rtr
import luminosity_table_detection as ltd

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


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

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setScene(QGraphicsScene(self))
        self._start_pos = None
        self._current_rect_item = None
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
        self.rectangleSelected.connect(self.get_main_window().on_rectangle_selected)
        self.lineModified.connect(self.get_main_window().on_line_modified)

    def get_main_window(self):
        """Traverse the parent hierarchy to get the QMainWindow (OCRApp) instance."""
        parent = self.parent()
        while parent is not None:
            if isinstance(parent, QMainWindow):  # Check if the parent is the QMainWindow
                return parent
            parent = parent.parent()
        raise RuntimeError("Main window (QMainWindow) not found in the parent hierarchy.")

    def pil_image_to_qimage(self, pil_image):
        """Convert PIL Image to QImage."""
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
            logger.error(f"Error loading PDF: {e}")

    def next_page(self):
        """Navigate to the next page of the PDF."""
        if self.current_page_index + 1 < len(self.pdf_images):
            self.current_page_index += 1
            self.load_image(self.pdf_images[self.current_page_index])

    def previous_page(self):
        """Navigate to the previous page of the PDF."""
        if self.current_page_index - 1 >= 0:
            self.current_page_index -= 1
            self.load_image(self.pdf_images[self.current_page_index])

    def load_image(self, image):
        """Load a QImage into the scene."""
        self.scene().clear()
        qt_image = QPixmap.fromImage(image)
        self._pixmap_item = QGraphicsPixmapItem(qt_image)
        self.scene().addItem(self._pixmap_item)
        self.fitInView(self._pixmap_item, Qt.KeepAspectRatio)
        self._rect_items.clear()
        self._line_items.clear()

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
            logger.error(f"Error in mousePressEvent: {e}")
            self.get_main_window().show_error_message(f"An error occurred: {e}")

    def mouseMoveEvent(self, event):
        try:
            if self._current_rect_item:
                rect = QRectF(self._start_pos, self.mapToScene(event.pos())).normalized()
                self._current_rect_item.setRect(rect)
            else:
                super().mouseMoveEvent(event)
        except Exception as e:
            logger.error(f"Error in mouseMoveEvent: {e}")
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
            logger.error(f"Error in mouseReleaseEvent: {e}")
            self.get_main_window().show_error_message(f"An error occurred: {e}")

    def get_cropped_areas(self):
        """ Returns the list of cropped areas """
        return self.cropped_areas
    
    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Delete:
            if self._rect_items:
                rect_item = self._rect_items.pop()
                self.scene().removeItem(rect_item)
            if self._line_items:
                selected_items = self.scene().selectedItems()
                for item in selected_items:
                    if isinstance(item, QGraphicsLineItem):
                        self.scene().removeItem(item)
                        self._line_items.remove(item)
                        self.lineModified.emit()
        elif event.key() == Qt.Key_Z and event.modifiers() & Qt.ControlModifier:
            self.undo_last_action()
        elif event.key() == Qt.Key_Right:
            self.next_page()
        elif event.key() == Qt.Key_Left:
            self.previous_page()
        else:
            super().keyPressEvent(event)

    def undo_last_action(self):
        if self._rect_items:
            rect_item = self._rect_items.pop()
            self.scene().removeItem(rect_item)

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
                                logger.error(f"Failed to load image: {file_path}")
                            else:
                                self.load_image(image)
                        else:
                            self.get_main_window().show_error_message("Invalid file type. Only PDF or image files supported.")
            else:
                self.get_main_window().show_error_message("Invalid file(s). Please drop local files only.")
        except Exception as e:
            self.get_main_window().show_error_message(f"An error occurred while dropping files: {e}")
            logger.error(f"Error in dropEvent: {e}")

class OcrGui(QObject):
    ocr_progress = pyqtSignal(int, int)
    ocr_completed = pyqtSignal(tuple)
    ocr_error = pyqtSignal(str)

class OCRApp(QMainWindow):
    ocr_completed = pyqtSignal(object)
    ocr_progress = pyqtSignal(int, int)  # current progress, total tasks
    ocr_error = pyqtSignal(str)

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
        self.last_csv_path = None  # Store the path of the last saved CSV
        self.project_folder = None  # Store the project folder path
        self.low_confidence_cells = []  # Store low-confidence OCR results
        self.table_detection_method = 'Peaks and Troughs'  # Default method
        self.init_ui()

        # Signals for OCR processing
        self.ocr_worker = OcrGui()
        self.ocr_worker.ocr_progress.connect(self.update_progress_bar)
        self.ocr_worker.ocr_completed.connect(self.on_ocr_completed)
        self.ocr_worker.ocr_error.connect(self.show_error_message)

    def init_ui(self):

        self.init_menu_bar()

        splitter = QSplitter(Qt.Horizontal)

        self.project_list = QListWidget()
        splitter.addWidget(self.project_list)
        self.project_list.currentRowChanged.connect(self.change_page)
        self.graphics_view = PDFGraphicsView(self)
        splitter.addWidget(self.graphics_view)

        splitter.setSizes([300, 1600])

        self.setCentralWidget(splitter)

        self.init_tool_bar()

        self.init_output_dock()

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        sys.stdout = EmittingStream(textWritten=self.normal_output_written)
        sys.stderr = EmittingStream(textWritten=self.error_output_written)

        self.setStyleSheet(f"font-size: {self.text_size}px;")

        self.ocr_completed.connect(self.on_ocr_completed)
        self.ocr_progress.connect(self.on_ocr_progress)
        self.ocr_error.connect(self.on_ocr_error)

        self.graphics_view.lineModified.connect(self.on_line_modified)

    def init_menu_bar(self):
        menu_bar = self.menuBar()
        # File Menu
        file_menu = menu_bar.addMenu('File')

        open_action = QAction('Open', self)
        open_action.setShortcut('Ctrl+O')
        open_action.triggered.connect(self.open_pdf)
        file_menu.addAction(open_action)

        save_as_action = QAction('Save As', self)
        save_as_action.setShortcut('Ctrl+S')
        save_as_action.triggered.connect(self.save_as)
        file_menu.addAction(save_as_action)

        exit_action = QAction('Exit', self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # View Menu
        view_menu = menu_bar.addMenu('View')

        # Text Size Submenu
        text_size_menu = view_menu.addMenu('Text Size')
        sizes = ['16', '18', '20', '22', '24', '26', '28', '30']
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
        how_to_use_action.triggered.connect(lambda: self.show_help_tab('How to Use', 'Instructions on how to use the application.'))
        help_menu.addAction(how_to_use_action)

        terms_action = QAction('Terms of Service', self)
        terms_action.triggered.connect(lambda: self.show_help_tab('Terms of Service', 'Terms of Service text goes here.'))
        help_menu.addAction(terms_action)

        license_action = QAction('License', self)
        license_action.triggered.connect(lambda: self.show_help_tab('License', 'License text goes here.'))
        help_menu.addAction(license_action)
            # Move Email CSV to Help Menu

    def init_tool_bar(self):
        tool_bar = QToolBar("Main Toolbar")
        self.addToolBar(Qt.TopToolBarArea, tool_bar)

        # Initialize OCR
        self.init_ocr_action = QAction('Initialize OCR', self)
        self.init_ocr_action.triggered.connect(self.initialize_ocr_engines)
        tool_bar.addAction(self.init_ocr_action)

        # Run OCR
        self.run_ocr_action = QAction('Run OCR', self)
        self.run_ocr_action.triggered.connect(self.run_ocr)
        tool_bar.addAction(self.run_ocr_action)

        # Zoom In
        self.zoom_in_action = QAction('+', self)
        self.zoom_in_action.triggered.connect(self.zoom_in)
        self.zoom_in_action.setEnabled(False)
        tool_bar.addAction(self.zoom_in_action)

        # Zoom Out
        self.zoom_out_action = QAction('-', self)
        self.zoom_out_action.triggered.connect(self.zoom_out)
        self.zoom_out_action.setEnabled(False)
        tool_bar.addAction(self.zoom_out_action)

        # Navigation: Previous Page and Next Page
        prev_button = QPushButton('Previous Page', self)
        prev_button.clicked.connect(self.previous_page)
        tool_bar.addWidget(prev_button)

        next_button = QPushButton('Next Page', self)
        next_button.clicked.connect(self.next_page)
        tool_bar.addWidget(next_button)

        # Toggle Editing Mode
        self.edit_mode_action = QAction('Editing Mode', self)
        self.edit_mode_action.setCheckable(True)
        self.edit_mode_action.setChecked(True)
        self.edit_mode_action.setEnabled(False)
        self.edit_mode_action.triggered.connect(self.toggle_edit_mode)
        tool_bar.addAction(self.edit_mode_action)

        # Cropping Mode Toggle
        self.cropping_mode_action = QAction('Cropping Mode', self)
        self.cropping_mode_action.setCheckable(True)
        self.cropping_mode_action.setChecked(False)
        self.cropping_mode_action.setEnabled(False)
        self.cropping_mode_action.triggered.connect(self.toggle_cropping_mode)
        tool_bar.addAction(self.cropping_mode_action)

        # Undo Action
        undo_action = QAction('Undo', self)
        undo_action.setShortcut('Ctrl+Z')
        undo_action.triggered.connect(self.graphics_view.undo_last_action)
        tool_bar.addAction(undo_action)

        # Detect Tables Action
        self.detect_tables_action = QAction('Detect Tables', self)
        self.detect_tables_action.triggered.connect(self.detect_tables)
        self.detect_tables_action.setEnabled(False)
        tool_bar.addAction(self.detect_tables_action)

        # Separator
        tool_bar.addSeparator()

        # Export to Excel
        self.export_excel_action = QAction('Export to Excel', self)
        self.export_excel_action.triggered.connect(self.export_to_excel)
        self.export_excel_action.setEnabled(False)  # Initially disabled
        tool_bar.addAction(self.export_excel_action)

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

    def update_progress_bar(self, tasks_completed, total_tasks):
        self.progress_bar.setValue(tasks_completed)

    def on_ocr_completed(self, result):
        all_table_data, processing_time = result
        self.status_bar.showMessage(f"OCR completed in {processing_time:.2f} seconds", 5000)

    def set_table_detection_method(self, method_name):
        self.table_detection_method = method_name
        self.status_bar.showMessage(f'Table Detection Method set to: {method_name}', 5000)

    def detect_tables(self):
        image = self.pdf_images[self.current_page_index]
        image_path = os.path.join('temp_gui', f'page_{self.current_page_index}.png')

        # Ensure the temp_gui directory exists
        os.makedirs('temp_gui', exist_ok=True)

        # Save the current page image to a file
        try:
            image.save(image_path)
        except Exception as e:
            self.show_error_message(f'Failed to save image: {e}')
            logger.error(f'Failed to save image: {e}')
            return

        # Check if there are any cropped areas
        cropped_areas = self.graphics_view.get_rectangles()

        # Process cropped areas if they exist, otherwise process the full image
        if cropped_areas:
            # Perform table detection on cropped sections only
            for cropped_area in cropped_areas:
                cropped_image = self.crop_image_pil(self.pdf_images[self.current_page_index], cropped_area)
                cropped_image_path = os.path.join('temp_gui', f'cropped_page_{self.current_page_index}.png')
                cropped_image.save(cropped_image_path)

                self.status_bar.showMessage('Performing table detection on cropped area...', 5000)
                QApplication.processEvents()

                try:
                    if self.table_detection_method == 'Peaks and Troughs':
                        horizontal_positions, vertical_positions, _ = ltd.find_table_peaks_troughs(
                            cropped_image_path,
                            horizontal_state="border",
                            vertical_state="border"
                        )
                    elif self.table_detection_method == 'Transitions':
                        horizontal_positions, vertical_positions, _ = ltd.find_table_transitions(
                            cropped_image_path,
                            threshold=15,
                            min_distance=10,
                            smoothing_window=5
                        )
                    else:
                        self.show_error_message('Invalid table detection method selected.')
                        return

                    # Convert positions to QLineF objects for drawing lines
                    lines = []
                    width, height = cropped_image.size

                    for y in horizontal_positions:
                        line = QLineF(0, y, width, y)
                        lines.append(line)
                    for x in vertical_positions:
                        line = QLineF(x, 0, x, height)
                        lines.append(line)

                    # Update the lines for the cropped area
                    self.lines[self.current_page_index] = lines

                    # Display updated lines on the cropped section in the preview
                    self.graphics_view.display_lines(lines)

                except Exception as e:
                    self.show_error_message(f'Table detection on cropped area failed: {e}')
                    logger.error(f'Table detection on cropped area failed: {e}')
                    return
        else:
            self.status_bar.showMessage('No cropped areas found, proceeding with full image detection.', 5000)

            # Perform table detection on the full image only if there are no cropped areas
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
            except Exception as e:
                self.show_error_message(f'Table detection on full image failed: {e}')
                logger.error(f'Table detection on full image failed: {e}')
                return

            # Convert positions to QLineF objects for drawing lines
            lines = []
            width, height = image.size

            for y in horizontal_positions:
                line = QLineF(0, y, width, y)
                lines.append(line)

            for x in vertical_positions:
                line = QLineF(x, 0, x, height)
                lines.append(line)

            # Store lines for the current page
            self.lines[self.current_page_index] = lines

            # Display lines on the full image in the preview
            self.graphics_view.display_lines(lines)

            # Update status bar
            self.status_bar.showMessage('Table detection completed.', 5000)
        
    def open_pdf(self):
        options = QFileDialog.Options()
        file_name, _ = QFileDialog.getOpenFileName(self, "Open File", "", "PDF Files (*.pdf);;Image Files (*.png);;All Files (*)", options=options)
        if file_name:
            self.process_files([file_name])

    def on_rectangle_selected(self, rect):
        """Handle the event when a rectangle is selected for cropping in the graphics view."""
        logger.info(f"Cropping area selected on page {self.current_page_index + 1}: {rect}")
        
        # Clear any previously selected rectangle (limit to one rectangle)
        self.graphics_view.clear_rectangles()
        
        # Save the current rectangle selection
        self.rectangles[self.current_page_index] = [rect]

        # Crop the selected area
        try:
            cropped_image = self.crop_image_pil(self.pdf_images[self.current_page_index], rect)
            cropped_image_path = os.path.join(self.project_folder, f"cropped_page_{self.current_page_index + 1}.png")
            
            # Save the cropped image
            cropped_image.save(cropped_image_path)
            logger.info(f"Cropped image saved to {cropped_image_path}")

            # Optionally: Preview the cropped image in a new window or part of the UI
            self.preview_cropped_image(cropped_image)

            # Update the status bar or show a message
            self.status_bar.showMessage(f"Cropped image saved as {cropped_image_path}", 5000)
        
        except Exception as e:
            logger.error(f"Error cropping image: {e}")
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
        logger.info(f"Line modified on page {self.graphics_view.current_page_index + 1}")
        
        # You can add additional logic here, such as saving the lines, updating the UI, etc.
        self.save_current_lines()

    def save_current_lines(self):
        """Save the current lines for the page."""
        lines = self.graphics_view.get_lines()
        self.lines[self.graphics_view.current_page_index] = lines
        logger.info(f"Lines saved for page {self.graphics_view.current_page_index + 1}")

    def change_page(self, current_page):
        """Handle page changes when a different page is selected from the project list."""
        if current_page < 0 or current_page >= len(self.pdf_images):
            return

        # Update the current page index and display the new page
        self.current_page_index = current_page
        self.show_current_page()

        # Restore any previously saved rectangles and lines for the new page
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

    def next_page(self):
        """Navigate to the next page and display it."""
        if self.current_page_index + 1 < len(self.image_file_paths):
            self.current_page_index += 1
            self.show_current_page()

    def previous_page(self):
        """Navigate to the previous page and display it."""
        if self.current_page_index - 1 >= 0:
            self.current_page_index -= 1
            self.show_current_page()

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
                self.show_error_message(f'Failed to save CSV: {e}')
  
    def process_files(self, file_paths):
        """Process files that are dropped or opened and load them into the project."""
        try:
            for file_path in file_paths:
                if not os.path.exists(file_path):
                    self.show_error_message(f"File not found: {file_path}")
                    logger.error(f"File not found: {file_path}")
                    continue

                if file_path not in self.recent_files:
                    self.recent_files.insert(0, file_path)
                    if len(self.recent_files) > 5:
                        self.recent_files = self.recent_files[:5]

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
                        logger.error(f"Error creating project folder: {e}")
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
                        logger.error(f"Error loading image from {file_path}: {e}")
                
                # Unsupported file type
                else:
                    self.show_error_message(f"Unsupported file type: {file_path}")
                    logger.error(f"Unsupported file type: {file_path}")

        except Exception as e:
            self.show_error_message(f"An error occurred while processing files: {e}")
            logger.error(f"Error in process_files: {e}")

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
            logger.info(f'Attempting to load PDF: {file_path}')
            self.pdf_images = convert_from_path(file_path, dpi=200)  # Lower DPI to manage memory usage
            total_pages = len(self.pdf_images)
            logger.info(f'Total pages in the PDF: {total_pages}')

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
            for idx in range(total_pages):
                self.project_list.addItem(f"Page {idx + 1}")

            # Display the first page initially
            self.show_current_page()
            self.status_bar.showMessage('PDF Loaded Successfully', 5000)

            # Enable actions once a PDF is loaded
            self.zoom_in_action.setEnabled(True)
            self.zoom_out_action.setEnabled(True)
            self.detect_tables_action.setEnabled(True)
            self.edit_mode_action.setEnabled(True)
            self.cropping_mode_action.setEnabled(True)

        except Exception as e:
            logger.error(f'Failed to load PDF: {e}', exc_info=True)
            QMessageBox.critical(self, 'Error', f'Failed to load PDF: {e}')
            self.status_bar.showMessage('Failed to load PDF', 5000)
            
    def load_image(self, image_path):
        try:
            image = Image.open(image_path)
            self.pdf_images = [image]
            self.current_page_index = 0
            self.rectangles = {}  # Reset rectangles
            self.lines = {}       # Reset lines
            self.show_current_page()
            self.status_bar.showMessage('Image Loaded Successfully', 5000)
            self.project_list.clear()
            self.project_list.addItem(os.path.basename(image_path))

            self.zoom_in_action.setEnabled(True)
            self.zoom_out_action.setEnabled(True)
            self.detect_tables_action.setEnabled(True)
            self.edit_mode_action.setEnabled(True)
            self.cropping_mode_action.setEnabled(True)
        except Exception as e:
            self.status_bar.showMessage('Failed to load Image')
            QMessageBox.critical(self, 'Error', f'Failed to load Image: {e}')

    def show_current_page(self):
        """Display the current page in the graphics view by loading it from disk."""
        try:
            # Check if the current page index is valid
            if not self.image_file_paths or self.current_page_index >= len(self.image_file_paths):
                logger.error(f'Invalid page index: {self.current_page_index}')
                return

            # Load the image for the current page from disk
            image_file_path = self.image_file_paths[self.current_page_index]
            image = Image.open(image_file_path)
            qimage = self.pil_image_to_qimage(image)  # Convert PIL Image to QImage
            self.graphics_view.load_image(qimage)

            # Log the successful loading of the page
            logger.info(f'Successfully displayed page {self.current_page_index + 1}')

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
            page_lines = self.lines.get(self.current_page_index, [])
            self.graphics_view.display_lines(page_lines)

        except Exception as e:
            logger.error(f"Failed to display page {self.current_page_index}: {e}", exc_info=True)
            self.show_error_message(f"An error occurred while displaying page {self.current_page_index}: {e}")

    def save_current_rectangles(self):
        rects = self.graphics_view.get_rectangles()
        self.rectangles[self.current_page_index] = rects

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
            threading.Thread(target=self.ocr_task).start()  # Start OCR task in a separate thread

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

            num_pages = len(self.pdf_images)
            avg_time = processing_time / num_pages if num_pages else 0
            self.status_bar.showMessage(f'OCR Completed. Average time per page: {avg_time:.2f} seconds', 5000)

        except Exception as e:
            logger.error(f"Critical error in OCR task: {e}")
            self.ocr_error.emit(f"Critical error: {e}")  # Emit error signal
        finally:
            self.ocr_running = False
            self.ocr_progress.emit(1, 1)  # Ensure progress is complete
            self.run_ocr_action.setText('Run OCR')
            
    def crop_image_pil(self, image, rect):
        width, height = image.size
        scene_width = self.graphics_view.scene().width()
        scene_height = self.graphics_view.scene().height()

        # Calculate the rectangle boundaries relative to the image size
        left = int(max(0, min(int(rect.left() / scene_width * width), width)))
        top = int(max(0, min(int(rect.top() / scene_height * height), height)))
        right = int(max(left + 1, min(int(rect.right() / scene_width * width), width)))  # Ensure valid crop box
        bottom = int(max(top + 1, min(int(rect.bottom() / scene_height * height), height)))  # Ensure valid crop box

        # Ensure the crop box is valid (right > left and bottom > top)
        if right > left and bottom > top:
            try:
                cropped_image = image.crop((left, top, right, bottom))
                return cropped_image
            except Exception as e:
                logger.error(f"Error cropping image: {e}")
                raise ValueError(f"Crop operation failed: {e}")
        else:
            logger.error(f"Invalid crop dimensions: {left}, {top}, {right}, {bottom}")
            raise ValueError("Crop dimensions are out of bounds or invalid.")

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
                        self.tableWidget.setItem(row_index, col_index, QTableWidgetItem(value))

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
        error_dialog.setStyleSheet("QLabel{min-width: 250px; font-size: 14px;}")  # Customize the appearance
        
        error_dialog.exec_()

        # Optionally, log the error
        logger.error(f"Error displayed: {message}")
        if detailed_message:
            logger.error(f"Details: {detailed_message}")

    def on_ocr_progress(self, current_progress, total_tasks):
        self.status_bar.showMessage(f'Processing OCR... ({current_progress}/{total_tasks})', 5000)
        self.progress_bar.setValue(current_progress)

    def on_ocr_completed(self, result):
        """
        Handles the completion of the OCR task in the GUI, including saving the results to a CSV,
        updating the GUI with performance statistics, and showing OCR quality information.
        """
        all_table_data, total, bad, easyocr_count, paddleocr_count, processing_time = result

        # Determine where to save the CSV
        if self.current_pdf_path:
            default_csv_name = os.path.splitext(os.path.basename(self.current_pdf_path))[0] + '.csv'
            default_csv_path = os.path.join(self.project_folder, default_csv_name)
        else:
            default_csv_path = ''
        
        csv_file_path = default_csv_path  # Save CSV directly into the project folder
        rtr.write_to_csv(all_table_data, csv_file_path)  # Write the table data to CSV

        # Read the CSV content and display it in the GUI's CSV output panel
        with open(csv_file_path, 'r') as f:
            csv_content = f.read()
            self.csv_output.setPlainText(csv_content)
        
        self.status_bar.showMessage(f"OCR Completed. Results saved to {csv_file_path}", 5000)
        self.last_csv_path = csv_file_path  # Store the path of the last saved CSV for later use
        self.export_excel_action.setEnabled(True)  # Enable the "Export to Excel" action

        # Display the OCR results in the table view
        self.display_table(all_table_data)

        # Cleanup temporary files used during OCR
        rtr.cleanup('temp_gui')
        self.status_bar.removeWidget(self.progress_bar)

        # Performance statistics
        num_pages = len(self.pdf_images)
        avg_time = processing_time / num_pages if num_pages else 0
        self.status_bar.showMessage(f'OCR Completed. Average time per page: {avg_time:.2f} seconds', 5000)

        # Quality statistics (for low-confidence results)
        if total > 0:
            percentage_low_confidence = (bad / total) * 100
            self.status_bar.showMessage(f"Percentage of results with less than 80% confidence: {percentage_low_confidence:.2f}% ({bad} low confidence)")
        else:
            self.status_bar.showMessage("No OCR results to process.")
        
        # Log the OCR engine usage summary
        self.status_bar.showMessage(f'OCR Engine Usage - EasyOCR: {easyocr_count}, PaddleOCR: {paddleocr_count}', 5000)

        # Update the project explorer to show the new files
        self.update_project_explorer()

        # Optional: Display detected language (assuming this functionality is in place)
        detected_language = 'English'  # Placeholder - Replace with actual detected language if available
        self.status_bar.showMessage(f'Detected Language: {detected_language}', 5000)

    def on_ocr_error(self, error_message):
        # Update status bar to reflect OCR failure
        self.status_bar.showMessage('OCR Failed', 5000)
        QMessageBox.critical(self, 'Error', f'OCR Failed: {error_message}')
        if self.progress_bar:
            self.status_bar.removeWidget(self.progress_bar)
            self.progress_bar = None 

    def show_help_tab(self, title, content):
        # Check if tab already exists
        for i in range(self.output_tabs.count()):
            if self.output_tabs.tabText(i) == title:
                self.output_tabs.setCurrentIndex(i)
                return
        # Create new tab
        text_edit = QTextEdit()
        text_edit.setReadOnly(True)
        text_edit.setPlainText(content)
        self.output_tabs.addTab(text_edit, title)
        self.output_tabs.setCurrentWidget(text_edit)

    def email_csv(self):
        if not self.last_csv_path or not os.path.exists(self.last_csv_path):
            self.show_error_message('No CSV file available to email. Please run OCR first.')
            return

        recipient, ok = QInputDialog.getText(self, 'Email CSV', 'Enter recipient email:')
        if ok and recipient:
            try:
                self.send_email(recipient, self.last_csv_path)
                QMessageBox.information(self, 'Email Sent', 'CSV file emailed successfully.')
            except Exception as e:
                self.show_error_message(f'Failed to send email: {e}')

    def send_email(self, recipient, attachment_path=None):
        subject = "OCR CSV Results"
        body = "Please find the attached CSV file with OCR results."

        # Create the mailto link
        mailto_link = f"mailto:{recipient}?subject={urllib.parse.quote(subject)}&body={urllib.parse.quote(body)}"

        # If there's an attachment, include a note in the body (Note: mailto does not support attachments directly)
        if attachment_path:
            attachment_note = f"\n\nPlease manually attach the file: {attachment_path}"
            mailto_link = f"mailto:{recipient}?subject={urllib.parse.quote(subject)}&body={urllib.parse.quote(body + attachment_note)}"

        # Open the default email client with the mailto link
        webbrowser.open(mailto_link)

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

    def update_project_explorer(self):
        self.project_list.clear()
        if self.project_folder:
            self.project_list.addItem(os.path.basename(self.project_folder))
            for item in os.listdir(self.project_folder):
                self.project_list.addItem(f"  - {item}")

    def cleanup_temp_images(self):
        """Delete all the temporary images saved on disk."""
        temp_dir = Path('temp_images')
        if temp_dir.exists():
            for file in temp_dir.iterdir():
                file.unlink()  # Delete the file
            temp_dir.rmdir()  # Remove the directory

    def closeEvent(self, event):
        self.cleanup_temp_images()
        event.accept()


def main():
    app = QApplication(sys.argv)

    try:
        with open("styles.qss", "r") as style_file:
            app.setStyleSheet(style_file.read())
    except FileNotFoundError:
        print("Style file not found. Proceeding without styles.")

    window = OCRApp()
    window.show()

    signal.signal(signal.SIGINT, signal.SIG_DFL)

    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
