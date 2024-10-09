# User Guide for OCR Application

## 1. Getting Started

When you launch the OCR Application, you'll be presented with an intuitive interface for OCR processing and data management. Here's how to begin:

### Launch the Application:
- Double-click the `OcrGui.py` file or run the command `python OcrGui.py` in your terminal. (This will change with the new installation process upon completion)

### Load a PDF File:
- Navigate to `File > Open` or press `Ctrl + O` to select and load a PDF document.

### Explore Features:
- Use the menu bar and toolbar to access OCR processing, editing, and data export functionalities.

## 2. User Interface Overview

The interface is divided into key sections:

- **Menu Bar**: Provides access to `File`, `Edit`, `View`, `Table Detection Method`, and `Help` menus.
- **Toolbar**: Quick access to actions like initializing and running OCR, undo/redo, and exporting data.
- **PDF Preview Pane**: Displays the loaded PDF, allowing you to navigate and edit.
- **Status Bar**: Shows information such as page number and processing status.

## 3. Opening a PDF File

You can load a PDF file into the application using the following methods:

- **Menu Bar**: Go to `File > Open` or use `Ctrl + O` to browse and select a PDF file.
- **Drag and Drop**: Drag a PDF file into the PDF Preview Pane.
- **Recent Files**: Access recently opened files via `File > Recent Files`.

## 4. Navigating Through Pages

Navigate through the PDF pages using:

### 4.1. Menu Bar Actions
- **Next Page**: `View > Next Page` or `Ctrl + Right Arrow`.
- **Previous Page**: `View > Previous Page` or `Ctrl + Left Arrow`.

### 4.2. Keyboard Shortcuts
- **Next Page**: `Ctrl + Right Arrow`.
- **Previous Page**: `Ctrl + Left Arrow`.

### 4.3. Status Bar Controls
- Some versions include clickable page numbers or navigation buttons in the status bar.

## 5. Running OCR Processing

Extract text and tables from your PDF by performing OCR.

### 5.1. Page Selection
- **Toolbar**: Click `Page Select` with the desired page range.

### 5.2. Table Detection
- **Toolbar**: Click `Detect Tables` with the page selected to visualise cells.

### 5.3. Run OCR
- **Toolbar**: Click `Run OCR`.
- **Menu Bar**: Go to `OCR > Run OCR`.

Monitor progress via the status bar. A notification will confirm completion, and extracted data will be available for review.

## 6. Editing PDF Content

You can annotate and edit the PDF for more accurate OCR results.

### 6.1. Adding Rectangles and Lines
- **Select Editing Mode**: Click the editing toggle button in the toolbar.
- **Add Rectangle/Line**: Choose the respective tool and draw on the PDF.

### 6.2. Undo and Redo Actions
- **Undo**: `Ctrl + Z` or `Edit > Undo`.
- **Redo**: `Ctrl + Y` or `Edit > Redo`.

## 7. Saving and Exporting Data

After running OCR, you can export the data.

### 7.1. Saving as CSV
- **Toolbar**: Click `Save CSV`.
- **Menu Bar**: `File > Save CSV`.

Choose the save location and receive a confirmation upon success.

### 7.2. Exporting to Excel
- **Toolbar**: Click `Export to Excel`.
- **Menu Bar**: `File > Export to Excel`.

Select the destination, and a notification will confirm the export.

## 8. Managing Recent Files

Quickly reopen recently accessed PDFs.

- **Recent Files**: Go to `File > Recent Files` and click a file from the list.

If a file has been moved or deleted, a warning will appear, and it will be removed from the list.

## 9. Settings and Preferences

Customise the application's behaviour for your needs.

### 9.1. Table Detection Methods
Choose different methods to detect tables:

- **Peaks and Troughs**: Detects tables based on structural peaks and troughs.
- **Transitions**: Identifies tables using text flow transitions.

Select a method via `Table Detection Method` in the menu bar.

### 9.2. Adjusting Text Size
Modify text size for better readability:

- **Menu Bar**: Go to `View > Text Size` and select a size (e.g., 16, 18, 20, etc.).

Text size will adjust immediately in the PDF Preview Pane.
