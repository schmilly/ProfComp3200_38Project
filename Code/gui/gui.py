import sys
import subprocess
import os
import mimetypes
from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout, QPushButton, QLabel, 
                             QFileDialog, QTableWidget, QTableWidgetItem, QProgressBar, 
                             QComboBox, QHBoxLayout, QFrame, QTextEdit, QSplitter, QSizePolicy,
                             QMenuBar, QMenu, QAction, QMessageBox)
from PyQt5.QtCore import Qt, QMimeData
from PyQt5.QtGui import QDragEnterEvent, QDropEvent, QPalette, QColor, QPixmap
from pdf2image import convert_from_path
import ocr

class OCRApp(QWidget):
    def __init__(self):
        super().__init__()
        self.text_size = 20
        self.initUI()
        
    def initUI(self):
        self.setWindowTitle('OCR PDF to Table')
        self.setGeometry(100, 100, 1200, 800)
        self.setAcceptDrops(True)

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
        
        self.label = QLabel('Drag and Drop a PDF file or use the button to browse')
        control_layout.addWidget(self.label)

        self.button = self.createButton('Browse PDF File', self.browse_file, QSizePolicy.Expanding, 50)
        control_layout.addWidget(self.button)
        
        layout.addLayout(control_layout)

    def createButton(self, text, callback, policy, height):
        button = QPushButton(text)
        button.setSizePolicy(policy, QSizePolicy.Fixed)
        button.setFixedHeight(height)
        button.clicked.connect(callback)
        return button

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
        self.progressBars = []

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

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if all(url.isLocalFile() and url.toLocalFile().endswith('.pdf') for url in urls):
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
                    if mime_type == 'application/pdf' and file_path.endswith('.pdf'):
                        valid_files.append(file_path)
            
            if valid_files:
                self.process_files(valid_files)
            else:
                self.show_error_message("Invalid file(s). Please drop PDF files only.")
        else:
            self.show_error_message("Invalid file(s). Please drop local files only.")

    def show_error_message(self, message):
        error_dialog = QMessageBox()
        error_dialog.setIcon(QMessageBox.Warning)
        error_dialog.setText(message)
        error_dialog.setWindowTitle("Invalid File")
        error_dialog.exec_()

    def browse_file(self):
        file_paths, _ = QFileDialog.getOpenFileNames(self, "Open PDF Files", "", "PDF Files (*.pdf);;All Files (*)")
        if file_paths:
            self.process_files(file_paths)

    def process_files(self, file_paths):
        self.totalProgressBar.setVisible(True)
        self.totalProgressBar.setValue(0)
        total_files = len(file_paths)
        completed_files = 0

        for progressBar in self.progressBars:
            self.layout().removeWidget(progressBar)
            progressBar.deleteLater()
        self.progressBars = []

        for file_path in file_paths:
            progressBar = QProgressBar()
            progressBar.setVisible(True)
            self.layout().insertWidget(self.layout().count() - 3, progressBar)  # Insert above comboBox, tableWidget, and timeLabel
            self.progressBars.append(progressBar)

            # Convert PDF to images
            output_folder = 'output_images'
            images = self.convert_pdf_to_images(file_path, output_folder)
            
            if images:
                pixmap = QPixmap(images[0])
                self.imagePreview.setPixmap(pixmap)
            
            # Load image preview
            tables, elapsed_time = ocr.ocr_pdf_to_table(file_path)
            
            progressBar.setValue(100)
            completed_files += 1
            self.totalProgressBar.setValue((completed_files / total_files) * 100)
            
            self.comboBox.clear()
            for i in range(len(tables)):
                self.comboBox.addItem(f'Table {i+1}')
            
            self.timeLabel.setText(f'Elapsed Time: {elapsed_time:.2f} seconds')
            self.timeLabel.setVisible(True)
            self.display_table(tables[0])

            # Display CSV text output
            csv_text = tables[0].to_csv(index=False)
            self.textOutput.setPlainText(csv_text)

    def convert_pdf_to_images(self, pdf_path, output_folder, image_format='png'):
        os.makedirs(output_folder, exist_ok=True)
        
        images = convert_from_path(pdf_path, output_folder=output_folder, fmt=image_format)
        image_files = [os.path.join(output_folder, f"page-{i}.{image_format}") for i in range(1, len(images) + 1)]
        
        return image_files

    def display_table(self, table):
        self.tableWidget.clear()
        self.tableWidget.setRowCount(table.shape[0])
        self.tableWidget.setColumnCount(table.shape[1])
        
        for i in range(table.shape[0]):
            for j in range(table.shape[1]):
                self.tableWidget.setItem(i, j, QTableWidgetItem(str(table.iat[i, j])))

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = OCRApp()
    window.show()
    sys.exit(app.exec_())
