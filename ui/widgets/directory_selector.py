"""
Directory selector widget for choosing directories to scan.
"""
from typing import List

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QWidget, QPushButton, QFileDialog, QHBoxLayout, 
    QVBoxLayout, QLabel, QListWidget, QListWidgetItem
)

class DirectorySelector(QWidget):
    """
    Widget that allows users to select one or more directories for scanning.
    
    Signals:
        directories_selected: Emitted when directories are selected with a list of paths
    """
    # Signal emitted when directories are selected
    directories_selected = Signal(list)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.selected_directories = []
        self.init_ui()
        
    def init_ui(self):
        """Initialize the user interface components."""
        # Main layout
        main_layout = QVBoxLayout(self)
        
        # Title label
        title_label = QLabel("Select Directories to Scan")
        title_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        main_layout.addWidget(title_label)
        
        # Button layout
        button_layout = QHBoxLayout()
        
        # Directory selection button
        self.select_button = QPushButton("Add Directory")
        self.select_button.clicked.connect(self.on_select_directory)
        button_layout.addWidget(self.select_button)
        
        # Remove selected button
        self.remove_button = QPushButton("Remove Selected")
        self.remove_button.clicked.connect(self.on_remove_selected)
        self.remove_button.setEnabled(False)  # Disabled until a directory is selected
        button_layout.addWidget(self.remove_button)
        
        # Clear button
        self.clear_button = QPushButton("Clear All")
        self.clear_button.clicked.connect(self.on_clear_directories)
        button_layout.addWidget(self.clear_button)
        
        # Scan button
        self.scan_button = QPushButton("Scan for Duplicates")
        self.scan_button.clicked.connect(self.on_scan_clicked)
        self.scan_button.setEnabled(False)  # Disabled until directories are selected
        button_layout.addWidget(self.scan_button)
        
        main_layout.addLayout(button_layout)
        
        # List of selected directories
        self.directory_list = QListWidget()
        self.directory_list.itemSelectionChanged.connect(self.on_selection_changed)
        main_layout.addWidget(self.directory_list)
        
        # Set layout
        self.setLayout(main_layout)
    
    def on_select_directory(self):
        """Open file dialog to select a directory and add it to the list."""
        directory = QFileDialog.getExistingDirectory(
            self, "Select Directory to Scan", "", QFileDialog.ShowDirsOnly
        )
        
        if directory:
            # Check if directory is already in the list
            if directory not in self.selected_directories:
                self.selected_directories.append(directory)
                self.directory_list.addItem(QListWidgetItem(directory))
                self.scan_button.setEnabled(True)
    
    def on_clear_directories(self):
        """Clear the list of selected directories."""
        self.selected_directories.clear()
        self.directory_list.clear()
        self.scan_button.setEnabled(False)
        self.remove_button.setEnabled(False)
        
    def on_remove_selected(self):
        """Remove the selected directory from the list."""
        selected_items = self.directory_list.selectedItems()
        if not selected_items:
            return
            
        # Get the selected item and its directory path
        selected_item = selected_items[0]
        selected_row = self.directory_list.row(selected_item)
        directory_path = selected_item.text()
        
        # Remove from the list widget
        self.directory_list.takeItem(selected_row)
        
        # Remove from the selected directories list
        if directory_path in self.selected_directories:
            self.selected_directories.remove(directory_path)
            
        # Disable the scan button if no directories remain
        if not self.selected_directories:
            self.scan_button.setEnabled(False)
            
        # Disable the remove button since the selection is now gone
        self.remove_button.setEnabled(False)
        
    def on_selection_changed(self):
        """Enable/disable the remove button based on selection state."""
        # Enable the remove button if an item is selected, disable otherwise
        self.remove_button.setEnabled(len(self.directory_list.selectedItems()) > 0)
    
    def on_scan_clicked(self):
        """Emit the directories_selected signal with selected directories."""
        if self.selected_directories:
            self.directories_selected.emit(self.selected_directories)
    
    def get_selected_directories(self) -> List[str]:
        """
        Get the list of currently selected directories.
        
        Returns:
            List of directory paths
        """
        return self.selected_directories