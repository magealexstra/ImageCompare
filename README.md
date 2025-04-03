# ImageCompare

A desktop application for finding and managing duplicate images using perceptual hashing technology.

## Description

ImageCompare is a powerful tool designed for quickly scanning directories to identify and remove duplicate images. Unlike simple byte-by-byte comparison, ImageCompare uses perceptual hashing to find images that look similar even if they have different file sizes, formats, or minor modifications.

This application is specifically designed for Kubuntu Linux (KDE Plasma/Qt) and uses PySide6 for the GUI components.

## Features

- **Multiple Directory Scanning**: Select and scan multiple directories for duplicate images
- **Perceptual Hash Comparison**: Identify visually similar images even with different formats or sizes
- **Interactive UI**: Side-by-side image comparison with selection capabilities
- **Safe Deletion**: Move unwanted duplicates to the system trash rather than permanent deletion
- **Progress Tracking**: Real-time progress display during scanning and hashing operations
- **User-Friendly Interface**: Intuitive layout with clear indicators for duplicate sets
- **Intelligent Auto-Selection**: Automatically suggests which duplicates to delete based on quality, size, and filename patterns
- **Skip Functionality**: Option to skip duplicate sets without deletion and continue to the next set
- **Adaptive Resource Management**: Optimizes CPU and memory usage based on your system's capabilities
- **Directory Management**: Add or remove individual directories from the scan list

## Installation

### Prerequisites

- Python 3.8 or higher
- PySide6, Pillow, ImageHash, send2trash, and psutil libraries
- At least 2GB RAM (4GB+ recommended for large image collections)

### Setup

1. Clone the repository:
   ```
   git clone https://github.com/yourusername/ImageCompare.git
   cd ImageCompare
   ```

2. Create a virtual environment (optional but recommended):
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

## Usage

1. Run the application:
   ```
   python main.py
   ```

2. Use the "Add Directory" button to select folders containing images to scan. You can remove individual directories using the "Remove Selected" button.

3. Click "Scan for Duplicates" to start the scanning process.

4. Once scanning completes, browse through the identified duplicate sets in the left panel.

5. Select a duplicate set to view the images side-by-side in the right panel.

6. You can use the "Auto-Select" button to automatically identify which images to delete based on quality, size, and filename patterns.

7. Check the boxes below images you want to remove, then click "Delete Selected Images". Selected images will be moved to the system trash.

8. If you want to keep all images in a particular set, click "Skip This Set" to move to the next set of duplicates.

9. You can adjust preferences for the auto-selection algorithm through the "Preferences" button.

## Project Structure

- `core/`: Core logic modules
  - `scanner.py`: Image file discovery
  - `hasher.py`: Perceptual hash calculation
  - `duplicate_finder.py`: Duplicate identification
  - `file_handler.py`: File operations (moving to trash)
  - `resource_manager.py`: Adaptive system resource management

- `ui/`: User interface components
  - `main_window.py`: Main application window
  - `widgets/`: Custom UI widgets
    - `directory_selector.py`: UI for selecting directories
    - `progress_display.py`: Progress bar and status display
    - `duplicate_list.py`: Widget for displaying duplicate sets
    - `image_compare.py`: Widget for comparing and selecting images
    - `preferences_dialog.py`: Settings for auto-selection algorithm
    - `image_loader.py`: Asynchronous image loading with caching

- `main.py`: Application entry point

## Dependencies

- [PySide6](https://wiki.qt.io/Qt_for_Python) - Python bindings for Qt GUI framework
- [Pillow](https://python-pillow.org/) - Python Imaging Library
- [ImageHash](https://github.com/JohannesBuchner/imagehash) - Perceptual image hashing library
- [send2trash](https://github.com/arsenetar/send2trash) - Cross-platform library for sending files to trash
- [psutil](https://github.com/giampaolo/psutil) - Cross-platform system monitoring and resource management

## Development

Refer to `PO1.md` for the complete project plan and implementation status.

## License

[MIT License](LICENSE)
