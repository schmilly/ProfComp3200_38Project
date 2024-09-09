import sys
import os
import mimetypes
from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout, QPushButton, QLabel, 
                             QFileDialog, QTableWidget, QTableWidgetItem, QProgressBar, 
                             QComboBox, QHBoxLayout, QFrame, QTextEdit, QSplitter, QSizePolicy,
                             QMenuBar, QMenu, QAction, QMessageBox)
from PyQt5.QtCore import Qt, QMimeData, QThread, pyqtSignal
from PyQt5.QtGui import QDragEnterEvent, QDropEvent, QPalette, QColor, QPixmap
from pdf2image import convert_from_path
from pdf_to_image import pdf_to_images
from PIL import Image
#import ocr  # Assuming `ocr` contains the function for OCR and table extraction

# Imports from the original script
from RunThroughRefactor import (setup_environment, convert_pdf_to_images, 
                                extract_tables_from_images, cellularize_tables,
                                initialize_paddleocr, initialize_easyocr, perform_ocr_on_images, 
                                write_to_csv, cleanup)


class OCRThread(QThread):
    progress_signal = pyqtSignal(int)  # To update progress bar
    result_signal = pyqtSignal(dict, int, int, int, int)  # To return results

    def __init__(self, file_path):
        super().__init__()
        self.file_path = file_path

    def run(self):
        storedir = "temp"
        setup_environment(storedir)

        # Initialize OCR engines
        ocr_engine = initialize_paddleocr()
        easyocr_engine = initialize_easyocr()

        # Convert PDF to images
        image_list = convert_pdf_to_images(Path(self.file_path), storedir)
        table_map = extract_tables_from_images(image_list)
        location_lists = cellularize_tables(image_list, table_map)

        # Perform OCR
        table_data, total, bad, easyocr_count, paddleocr_count = perform_ocr_on_images(location_lists, ocr_engine, easyocr_engine)

        # Write results to CSV (optional)
        output_csv = 'output.csv'
        write_to_csv(table_data, output_csv)

        # Emit results
        self.result_signal.emit(table_data, total, bad, easyocr_count, paddleocr_count)

        # Clean up temporary files
        cleanup(storedir)


class OCRApp(QWidget):
    def __init__(self):
        super().__init__()
        self.text_size = 20
        self.initUI()
        
    def initUI(self):
        self.setWindowTitle('OCR PDF to Table')
        self.setGeometry(100, 100, 1200, 800)

        main_layout = QVBoxLayout()
        self.initMenuBar(main_layout)
        self.initTopControls(main_layout)
        self.initSplitter(main_layout)
        self.initProgressBars(main_layout)
        self.initTable(main_layout)
        
        self.setLayout(main_layout)
        self.set_dark_mode(self.text_size)

    def initMenuBar(self, layout):
        menu_layout = QHBoxLayout()
        
        # Menu bar
        self.menuBar = QMenuBar(self)
        self.settingsMenu = QMenu("Settings", self)
        self.menuBar.addMenu(self.settingsMenu)
        
        self.textSizeMenu = self.addSubMenu(self.settingsMenu, "Change Text Size", 
                                            [("Small", 20), ("Medium", 24), ("Large", 30)], 
                                            self.change_text_size)
        
        self.addMenuAction(self.settingsMenu, "Light Mode", lambda: self.set_light_mode(self.text_size))
        self.addMenuAction(self.settingsMenu, "Dark Mode", lambda: self.set_dark_mode(self.text_size))
        
        menu_layout.addWidget(self.menuBar)
        layout.addLayout(menu_layout)

    def addSubMenu(self, parentMenu, title, actions, callback):
        subMenu = QMenu(title, self)
        parentMenu.addMenu(subMenu)
        for name, size in actions:
            action = QAction(name, self)
            action.triggered.connect(lambda _, s=size: callback(s))
            subMenu.addAction(action)
        return subMenu

    def addMenuAction(self, menu, title, callback):
        action = QAction(title, self)
        action.triggered.connect(callback)
        menu.addAction(action)

    def initTopControls(self, layout):
        control_layout = QHBoxLayout()
        
        self.label = QLabel('Drag and Drop a PDF or PNG file onto the button below:')
        control_layout.addWidget(self.label)

        self.dropButton = FileDropButton('Drop File Here', self)
        self.dropButton.setFixedSize(200, 100)
        control_layout.addWidget(self.dropButton)
        
        layout.addLayout(control_layout)

    def initSplitter(self, layout):
        splitter = QSplitter(Qt.Horizontal)
        self.imagePreview = self.createPreviewLabel('PDF/Image Preview')
        self.textOutput = self.createTextEdit('CSV Text Output')

        splitter.addWidget(self.imagePreview)
        splitter.addWidget(self.textOutput)
        layout.addWidget(splitter)

    def createPreviewLabel(self, text):
        label = QLabel(text)
        label.setFrameShape(QFrame.Box)
        label.setScaledContents(True)
        label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        return label

    def createTextEdit(self, text):
        textEdit = QTextEdit(text)
        textEdit.setFrameShape(QFrame.Box)
        textEdit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        return textEdit

    def initProgressBars(self, layout):
        self.totalProgressBar = QProgressBar()
        self.totalProgressBar.setVisible(False)
        layout.addWidget(self.totalProgressBar)

    def initTable(self, layout):
        self.comboBox = QComboBox()
        self.comboBox.addItem('Table 1')
        self.comboBox.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        layout.addWidget(self.comboBox)

        self.tableWidget = QTableWidget()
        self.tableWidget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout.addWidget(self.tableWidget)

        self.timeLabel = QLabel('Elapsed Time: 0.00 seconds')
        self.timeLabel.setVisible(False)
        layout.addWidget(self.timeLabel)


    def change_text_size(self, size):
        self.text_size = size
        self.update_stylesheet()

    def update_stylesheet(self):
        self.setStyleSheet(f"""
            QWidget {{
                background-color: #353535;
                color: white;
                font-family: 'MS Shell Dlg 2';
                font-size: {self.text_size}px;
                border: 1px solid #fff;
            }}
            QPushButton, QComboBox, QProgressBar, QTableWidget, QLabel, QTextEdit {{
                background-color: #454545;
                border: 2px outset #fff;
                font-size: {self.text_size}px;
                padding: 5px;
            }}
            QPushButton:pressed, QComboBox:pressed, QProgressBar:pressed, QTableWidget:pressed, QLabel:pressed, QTextEdit:pressed {{
                border: 2px inset #fff;
            }}
        """)

    def set_light_mode(self, text_size):
        palette = QPalette()
        palette.setColor(QPalette.Window, QColor(255, 255, 255))
        palette.setColor(QPalette.WindowText, QColor(0, 0, 0))
        self.setPalette(palette)

        self.setStyleSheet(f"""
            QWidget {{
                background-color: #FFFFFF;
                color: black;
                font-family: 'MS Shell Dlg 2';
                font-size: {text_size}px;
                border: 1px solid #000;
            }}
            QPushButton, QComboBox, QProgressBar, QTableWidget, QLabel, QTextEdit {{
                background-color: #FFFFFF;
                border: 2px outset #000;
                font-size: {text_size}px;
                padding: 5px;
            }}
            QPushButton:pressed, QComboBox:pressed, QProgressBar:pressed, QTableWidget:pressed, QLabel:pressed, QTextEdit:pressed {{
                border: 2px inset #000;
            }}
        """)

    def set_dark_mode(self, text_size):
        palette = QPalette()
        palette.setColor(QPalette.Window, QColor(53, 53, 53))
        palette.setColor(QPalette.WindowText, QColor(255, 255, 255))
        self.setPalette(palette)

        self.setStyleSheet(f"""
            QWidget {{
                background-color: #353535;
                color: white;
                font-family: 'MS Shell Dlg 2';
                font-size: {text_size}px;
                border: 1px solid #fff;
            }}
            QPushButton, QComboBox, QProgressBar, QTableWidget, QLabel, QTextEdit {{
                background-color: #454545;
                border: 2px outset #fff;
                font-size: {text_size}px;
                padding: 5px;
            }}
            QPushButton:pressed, QComboBox:pressed, QProgressBar:pressed, QTableWidget:pressed, QLabel:pressed, QTextEdit:pressed {{
                border: 2px inset #fff;
            }}
        """)

    def process_files(self, file_paths):
        if file_paths:
            file_path = file_paths[0]  # Process one file at a time

            # Start OCR process in a background thread
            self.totalProgressBar.setVisible(True)
            self.totalProgressBar.setValue(0)
            
            self.ocr_thread = OCRThread(file_path)
            self.ocr_thread.progress_signal.connect(self.update_progress)
            self.ocr_thread.result_signal.connect(self.display_results)
            self.ocr_thread.start()

    def update_progress(self, value):
        self.totalProgressBar.setValue(value)

    def show_images(self, images):
        if images:
            pixmap = self.pil2pixmap(images[0])  # Display the first image
            self.imagePreview.setPixmap(pixmap)

    def display_results(self, table_data, total, bad, easyocr_count, paddleocr_count):
        self.comboBox.clear()
        for i in range(total):
            self.comboBox.addItem(f'Table {i+1}')

        # Display a summary of the results in the CSV Text Output area
        summary = f"Results saved to CSV. EasyOCR: {easyocr_count}, PaddleOCR: {paddleocr_count}"
        self.textOutput.setPlainText(summary)

        # Display the first table in the table widget
        if table_data:
            self.display_table(list(table_data.values())[0])  # Show the first table

    def display_table(self, table):
        self.tableWidget.clear()
        self.tableWidget.setRowCount(len(table))
        self.tableWidget.setColumnCount(len(table[0]) if table else 0)
        
        for i, row in enumerate(table):
            for j, cell in enumerate(row):
                self.tableWidget.setItem(i, j, QTableWidgetItem(str(cell)))

    def show_error_message(self, message):
        error_dialog = QMessageBox()
        error_dialog.setIcon(QMessageBox.Warning)
        error_dialog.setText(message)
        error_dialog.setWindowTitle("Invalid File")
        error_dialog.exec_()


class FileDropButton(QPushButton):
    def __init__(self, title, parent=None):
        super().__init__(title, parent)
        self.setAcceptDrops(True)
        self.default_image = QPixmap() 
        self.dragged_image = QPixmap()

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if all(url.isLocalFile() and (url.toLocalFile().endswith('.pdf') or url.toLocalFile().endswith('.png')) for url in urls):
                event.acceptProposedAction()
            else:
                event.ignore()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            valid_files = []
            for url in urls:
                if url.isLocalFile():
                    file_path = url.toLocalFile()
                    mime_type, _ = mimetypes.guess_type(file_path)
                    if mime_type in ['application/pdf', 'image/png']:
                        valid_files.append(file_path)
            
            if valid_files:
                self.parent().process_files(valid_files)
            else:
                self.parent().show_error_message("Invalid file(s). Please drop PDF or PNG files only.")
            self.update_button_image(self.default_image)
        else:
            self.parent().show_error_message("Invalid file(s). Please drop local files only.")

    def update_button_image(self, pixmap):
        if pixmap.isNull():
            self.setText("Drop File Here")
        else:
            self.setIcon(pixmap)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = OCRApp()
    window.show()
    sys.exit(app.exec_())
