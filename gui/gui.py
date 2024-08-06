import sys
from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout, QPushButton, QLabel, 
                             QFileDialog, QTableWidget, QTableWidgetItem, QProgressBar, 
                             QComboBox, QHBoxLayout, QFrame, QTextEdit, QSplitter, QSizePolicy,
                             QMenuBar, QMenu, QAction, QInputDialog)
from PyQt5.QtCore import Qt, QMimeData
from PyQt5.QtGui import QDragEnterEvent, QDropEvent, QPalette, QColor, QPixmap
import ocr

class OCRApp(QWidget):
    def __init__(self):
        super().__init__()
        self.text_size = 20
        self.initUI()
        
    def initUI(self):
        self.setWindowTitle('OCR PDF to Table - Windows 95 Style')
        self.setGeometry(100, 100, 1200, 800)
        self.setAcceptDrops(True)
        
        main_layout = QVBoxLayout()

        # Menu bar
        self.menuBar = QMenuBar(self)
        self.settingsMenu = QMenu("Settings", self)
        self.menuBar.addMenu(self.settingsMenu)
        
        # Text Size Submenu
        self.textSizeMenu = QMenu("Change Text Size", self)
        self.settingsMenu.addMenu(self.textSizeMenu)
        
        self.smallTextAction = QAction('Small', self)
        self.mediumTextAction = QAction('Medium', self)
        self.largeTextAction = QAction('Large', self)
        
        self.textSizeMenu.addAction(self.smallTextAction)
        self.textSizeMenu.addAction(self.mediumTextAction)
        self.textSizeMenu.addAction(self.largeTextAction)
        
        self.smallTextAction.triggered.connect(lambda: self.change_text_size(20))
        self.mediumTextAction.triggered.connect(lambda: self.change_text_size(24))
        self.largeTextAction.triggered.connect(lambda: self.change_text_size(30))

        # Additional actions can be added here
        self.lightModeAction = QAction('Light Mode', self)
        self.darkModeAction = QAction('Dark Mode', self)
        self.settingsMenu.addAction(self.lightModeAction)
        self.settingsMenu.addAction(self.darkModeAction)
        self.lightModeAction.triggered.connect(lambda: self.set_light_mode(self.text_size))
        self.darkModeAction.triggered.connect(lambda: self.set_dark_mode(self.text_size))

        main_layout.setMenuBar(self.menuBar)
        
        self.label = QLabel('Drag and Drop a PDF file or use the button to browse')
        main_layout.addWidget(self.label)
        
        self.button = QPushButton('Browse PDF File')
        self.button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.button.setFixedHeight(50)
        self.button.clicked.connect(self.browse_file)
        main_layout.addWidget(self.button)
        
        self.totalProgressBar = QProgressBar()
        self.totalProgressBar.setVisible(False)
        main_layout.addWidget(self.totalProgressBar)

        self.progressBars = []

        splitter = QSplitter(Qt.Horizontal)
        
        self.imagePreview = QLabel('PDF/Image Preview')
        self.imagePreview.setFrameShape(QFrame.Box)
        self.imagePreview.setScaledContents(True)
        self.imagePreview.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        splitter.addWidget(self.imagePreview)
        
        self.textOutput = QTextEdit('CSV Text Output')
        self.textOutput.setFrameShape(QFrame.Box)
        self.textOutput.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        splitter.addWidget(self.textOutput)

        main_layout.addWidget(splitter)
        
        self.comboBox = QComboBox()
        self.comboBox.addItem('Table 1')
        self.comboBox.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        main_layout.addWidget(self.comboBox)
        
        self.tableWidget = QTableWidget()
        self.tableWidget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        main_layout.addWidget(self.tableWidget)
        
        self.timeLabel = QLabel('Elapsed Time: 0.00 seconds')
        self.timeLabel.setVisible(False)
        main_layout.addWidget(self.timeLabel)
        
        self.setLayout(main_layout)
        
        self.set_dark_mode(self.text_size)

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
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        for url in event.mimeData().urls():
            if url.isLocalFile():
                file_path = url.toLocalFile()
                self.process_file(file_path)

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

            # Load image preview
            pixmap = QPixmap(file_path)
            self.imagePreview.setPixmap(pixmap)
            
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
