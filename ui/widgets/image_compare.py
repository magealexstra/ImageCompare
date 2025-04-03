"""
Image compare widget for displaying and comparing duplicate images.
"""
import os
import subprocess
import re  # For extracting resolution from filenames
from typing import List, Dict, Optional

from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QPixmap, QImage
from PySide6.QtWidgets import (
    QWidget, QLabel, QCheckBox, QPushButton, QScrollArea,
    QVBoxLayout, QHBoxLayout, QGridLayout, QMessageBox,
    QFrame, QSizePolicy, QProgressBar
)

from ui.widgets.preferences_dialog import PreferencesDialog, PreferencesManager
from ui.widgets.image_loader import ImageLoader

class ImageCompare(QWidget):
    """
    Widget that displays multiple images side-by-side for comparison,
    with checkboxes to select images for deletion.
    
    Signals:
        delete_requested: Emitted when delete button is clicked with a list of paths to delete
    """
    # Signal emitted when delete button is clicked
    delete_requested = Signal(list)
    # Signal emitted when skip button is clicked
    skip_requested = Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.image_paths = []
        self.image_widgets = {}  # Dictionary to store references to image widgets
        
        # Create image loader for asynchronous loading
        self.image_loader = ImageLoader(self)
        
        # Image size for thumbnails
        self.thumbnail_size = QSize(300, 300)
        
        self.init_ui()
    
    def init_ui(self):
        """Initialize the user interface components."""
        # Main layout
        self.main_layout = QVBoxLayout(self)
        
        # Title label
        title_label = QLabel("Image Comparison")
        title_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        self.main_layout.addWidget(title_label)
        
        # Create scroll area for images
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        # Container widget for the scroll area
        self.scroll_widget = QWidget()
        self.scroll_area.setWidget(self.scroll_widget)
        
        # Grid layout for images
        self.grid_layout = QGridLayout(self.scroll_widget)
        self.grid_layout.setSpacing(10)
        
        self.main_layout.addWidget(self.scroll_area)
        
        # Button layout
        button_layout = QHBoxLayout()
        
        # Select all button
        self.select_all_button = QPushButton("Select All")
        self.select_all_button.clicked.connect(self.select_all_images)
        button_layout.addWidget(self.select_all_button)
        
        # Deselect all button
        self.deselect_all_button = QPushButton("Deselect All")
        self.deselect_all_button.clicked.connect(self.deselect_all_images)
        button_layout.addWidget(self.deselect_all_button)
        
        # Action buttons section
        action_buttons_layout = QHBoxLayout()
        
        # Auto-select button
        self.auto_select_button = QPushButton("Auto-Select")
        self.auto_select_button.clicked.connect(self.auto_select_images)
        self.auto_select_button.setStyleSheet("background-color: #4CAF50; color: white;")
        action_buttons_layout.addWidget(self.auto_select_button)
        
        # Preferences button
        self.prefs_button = QPushButton("Preferences")
        self.prefs_button.clicked.connect(self.show_preferences)
        self.prefs_button.setToolTip("Configure auto-select pattern preferences")
        action_buttons_layout.addWidget(self.prefs_button)
        
        # Open folder button
        self.open_folder_button = QPushButton("Open Folder")
        self.open_folder_button.clicked.connect(self.open_selected_folder)
        self.open_folder_button.setToolTip("Open the folder containing the selected image")
        self.open_folder_button.setStyleSheet("background-color: #2196F3; color: white;")
        action_buttons_layout.addWidget(self.open_folder_button)
        
        button_layout.addLayout(action_buttons_layout)
        
        # Auto-select checkbox
        self.auto_select_checkbox = QCheckBox("Auto-select on load")
        self.auto_select_checkbox.setToolTip("Automatically select images for deletion when a new set is loaded")
        self.auto_select_checkbox.setChecked(True)  # Enabled by default
        button_layout.addWidget(self.auto_select_checkbox)
        
        # Spacer
        button_layout.addStretch()
        
        # Skip confirmation checkbox
        self.skip_confirm_checkbox = QCheckBox("Skip confirmation")
        self.skip_confirm_checkbox.setToolTip("Delete selected images without confirmation popup")
        button_layout.addWidget(self.skip_confirm_checkbox)
        
        # Skip button
        self.skip_button = QPushButton("Skip This Set")
        self.skip_button.clicked.connect(self.on_skip_clicked)
        self.skip_button.setStyleSheet("background-color: #FF9800; color: white;")
        self.skip_button.setToolTip("Skip this duplicate set without deleting any files")
        button_layout.addWidget(self.skip_button)
        
        # Delete button
        self.delete_button = QPushButton("Delete Selected Images")
        self.delete_button.clicked.connect(self.on_delete_clicked)
        self.delete_button.setStyleSheet("background-color: #f44336; color: white;")
        button_layout.addWidget(self.delete_button)
        
        self.main_layout.addLayout(button_layout)
        
        # Set layout
        self.setLayout(self.main_layout)
    
    def set_images(self, image_paths: List[str]):
        """
        Set the images to display for comparison.
        Uses asynchronous loading for better UI responsiveness.
        
        Args:
            image_paths: List of paths to images in the duplicate set
        """
        # Clear previous images
        self.clear_images()
        
        # Store new paths
        self.image_paths = image_paths
        
        # Start preloading the next few duplicate sets (if parent has them)
        if hasattr(self.parent(), 'duplicate_list') and hasattr(self.parent().duplicate_list, 'duplicate_sets'):
            self.preload_next_sets()
        
        # Calculate grid dimensions
        # Try to display max 3 images per row for better comparison
        max_columns = 3
        
        # Create image widgets and add to grid
        for i, path in enumerate(image_paths):
            row = i // max_columns
            col = i % max_columns
            
            # Create image widget
            image_widget = self.create_image_widget(path)
            self.grid_layout.addWidget(image_widget, row, col)
            
            # Store reference to widget
            self.image_widgets[path] = image_widget
            
        # Run auto-select if checkbox is checked
        if self.auto_select_checkbox.isChecked():
            self.auto_select_images()
    
    def create_image_widget(self, image_path: str) -> QWidget:
        """
        Create a widget for displaying an image with checkbox and info.
        Uses asynchronous loading for better UI responsiveness.
        
        Args:
            image_path: Path to the image file
            
        Returns:
            Widget containing the image, checkbox and information
        """
        # Container widget
        container = QFrame()
        container.setFrameShape(QFrame.StyledPanel)
        container.setFrameShadow(QFrame.Raised)
        container.setLineWidth(1)
        
        # Layout for the container
        layout = QVBoxLayout(container)
        
        # Image display
        image_label = QLabel()
        image_label.setAlignment(Qt.AlignCenter)
        
        # Create a loading placeholder
        loading_label = QLabel("Loading...")
        loading_label.setAlignment(Qt.AlignCenter)
        loading_label.setStyleSheet("font-style: italic; color: #666;")
        
        # Progress indicator
        progress = QProgressBar()
        progress.setRange(0, 0)  # Indeterminate progress
        progress.setMaximumHeight(5)
        progress.setTextVisible(False)
        
        # Add loading indicator to layout
        layout.addWidget(loading_label)
        layout.addWidget(progress)
        layout.addWidget(image_label)
        
        # Hide actual image label until loaded
        image_label.hide()
        
        # Start asynchronous loading of image
        def image_loaded_callback(path, pixmap, is_thumbnail):
            # This is called when the image is loaded
            if path == image_path:
                # Update the image
                image_label.setPixmap(pixmap)
                
                # Show image and hide loading indicators
                loading_label.hide()
                progress.hide()
                image_label.show()
                
        # Queue the image for loading
        self.image_loader.load_image(
            image_path=image_path,
            target_size=self.thumbnail_size,
            callback=image_loaded_callback,
            priority=10,  # High priority for visible images
            load_full_res=True  # Load full resolution after thumbnail
        )
        
        # Set a minimum size policy
        image_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        image_label.setMinimumSize(300, 220)
        
        layout.addWidget(image_label)
        
        # File info layout
        info_layout = QVBoxLayout()
        
        # File name
        filename = os.path.basename(image_path)
        name_label = QLabel(f"<b>{filename}</b>")
        name_label.setWordWrap(True)
        info_layout.addWidget(name_label)
        
        # File path (shortened)
        path_label = QLabel(image_path)
        path_label.setWordWrap(True)
        path_label.setStyleSheet("font-size: 10px; color: #666;")
        info_layout.addWidget(path_label)
        
        # Try to get file size
        try:
            size_bytes = os.path.getsize(image_path)
            size_kb = size_bytes / 1024
            size_mb = size_kb / 1024
            
            if size_mb >= 1:
                size_str = f"{size_mb:.2f} MB"
            else:
                size_str = f"{size_kb:.2f} KB"
                
            size_label = QLabel(f"Size: {size_str}")
            info_layout.addWidget(size_label)
        except:
            pass
        
        layout.addLayout(info_layout)
        
        # Checkbox for selection
        checkbox = QCheckBox("Delete this image")
        checkbox.setObjectName(f"checkbox_{image_path}")
        layout.addWidget(checkbox)
        
        container.setLayout(layout)
        return container
    
    def clear_images(self):
        """Clear all displayed images."""
        # Remove all widgets from the grid
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        
        # Clear stored references
        self.image_widgets = {}
        self.image_paths = []
        
        # Cancel any pending image loads
        # (The image_loader will continue running but discard results)
    
    def get_selected_images(self) -> List[str]:
        """
        Get the list of selected images (checked for deletion).
        
        Returns:
            List of paths to the selected images
        """
        selected = []
        
        for path, widget in self.image_widgets.items():
            # Find the checkbox within the widget
            checkbox = widget.findChild(QCheckBox, f"checkbox_{path}")
            if checkbox and checkbox.isChecked():
                selected.append(path)
        
        return selected
    
    def select_all_images(self):
        """Select all images for deletion."""
        for path, widget in self.image_widgets.items():
            checkbox = widget.findChild(QCheckBox, f"checkbox_{path}")
            if checkbox:
                checkbox.setChecked(True)
    
    def deselect_all_images(self):
        """Deselect all images."""
        for path, widget in self.image_widgets.items():
            checkbox = widget.findChild(QCheckBox, f"checkbox_{path}")
            if checkbox:
                checkbox.setChecked(False)
    
    def auto_select_images(self):
        """
        Automatically select images for deletion based on file size and filename patterns.
        This method ONLY checks the boxes for recommended deletions but does not delete files.
        
        Heuristics used to identify likely duplicates:
        1. Smaller file sizes are more likely to be selected for deletion
        2. Files with patterns like "(1)", "copy", etc. in the filename are preferred for deletion
        3. Files with user-defined preferred patterns receive bonus points
        """
        if not self.image_paths:
            return
        
        # Reset selections first
        self.deselect_all_images()
        
        # Get file information for scoring
        file_info = []
        for path in self.image_paths:
            try:
                size = os.path.getsize(path)
                filename = os.path.basename(path)
                extension = os.path.splitext(filename)[1].lower()
                
                # Extract all useful information from filename
                file_metrics = self.extract_file_metrics(path, filename)
                
                # Create info dictionary with all extracted metrics
                info = {
                    'path': path,
                    'size': size,
                    'filename': filename,
                    'extension': extension,
                    'score': 0  # Higher score = more likely to be kept (not deleted)
                }
                
                # Add all extracted metrics
                info.update(file_metrics)
                
                file_info.append(info)
            except Exception as e:
                # Skip files with errors
                print(f"Error processing {path}: {str(e)}")
                continue
        
        if not file_info:
            return  # No valid files to process
        
        # Print initial file info
        print("\n--- Debug: Auto-Select Scoring ---")
        for info in file_info:
            print(f"File: {os.path.basename(info['path'])}")
            print(f"  Size: {info['size']} bytes")
            
            # Print identified metrics
            if 'resolution_width' in info and info['resolution_width'] > 0:
                source = info.get('resolution_source', 'unknown')
                print(f"  Resolution: {info['resolution_width']}x{info['resolution_height']} (source: {source})")
            if 'language_code' in info and info['language_code']:
                print(f"  Language: {info['language_code']}")
            if 'quality_indicators' in info and info['quality_indicators']:
                print(f"  Quality indicators: {', '.join(info['quality_indicators'])}")
            if 'duplicate_indicators' in info and info['duplicate_indicators']:
                print(f"  Duplicate indicators: {', '.join(info['duplicate_indicators'])}")
            
        # Apply scoring based on multiple factors
        self.score_files(file_info)
        
        # Print final scores
        print("\n--- Final Scores ---")
        for info in file_info:
            print(f"File: {os.path.basename(info['path'])}, Final Score: {info['score']:.2f}")
            
        # Sort by score (ascending, so lower scores come first)
        file_info.sort(key=lambda x: x['score'])
        
        # Print sorted order
        print("\n--- Sorted Order (lowest to highest score) ---")
        for i, info in enumerate(file_info):
            status = "KEEP" if i == len(file_info)-1 else "DELETE"
            print(f"{status}: {os.path.basename(info['path'])}, Score: {info['score']:.2f}")
        
        # Select all but the highest-scored file
        if len(file_info) > 1:
            # Always keep the highest-scored file
            files_to_delete = [info['path'] for info in file_info[:-1]]
            
            # Set checkboxes for files to delete (just checking boxes, not deleting)
            for path in files_to_delete:
                widget = self.image_widgets.get(path)
                if widget:
                    checkbox = widget.findChild(QCheckBox, f"checkbox_{path}")
                    if checkbox:
                        checkbox.setChecked(True)
    def extract_file_metrics(self, path: str, filename: str) -> dict:
        """
        Extract various metrics from a file to use in scoring.
        Uses multiple approaches to identify important characteristics.
        
        Args:
            path: Full path to the file
            filename: Basename of the file
            
        Returns:
            Dictionary with extracted metrics
        """
        metrics = {}
        
        # 1. Extract actual image dimensions by loading the image
        try:
            # Use QImage to get actual dimensions of the image
            image = QImage(path)
            if not image.isNull():
                # Successfully loaded the image
                width = image.width()
                height = image.height()
                metrics['resolution_width'] = width
                metrics['resolution_height'] = height
                metrics['resolution_pixels'] = width * height
                metrics['resolution_source'] = 'actual'
            else:
                # Fall back to filename pattern if image loading fails
                res_match = re.search(r'(\d+)x(\d+)', filename)
                if res_match:
                    metrics['resolution_width'] = int(res_match.group(1))
                    metrics['resolution_height'] = int(res_match.group(2))
                    metrics['resolution_pixels'] = metrics['resolution_width'] * metrics['resolution_height']
                    metrics['resolution_source'] = 'filename'
                else:
                    metrics['resolution_width'] = 0
                    metrics['resolution_height'] = 0
                    metrics['resolution_pixels'] = 0
                    metrics['resolution_source'] = 'none'
        except Exception as e:
            # If there's an error loading the image, fall back to filename method
            print(f"Error loading image dimensions for {filename}: {str(e)}")
            res_match = re.search(r'(\d+)x(\d+)', filename)
            if res_match:
                metrics['resolution_width'] = int(res_match.group(1))
                metrics['resolution_height'] = int(res_match.group(2))
                metrics['resolution_pixels'] = metrics['resolution_width'] * metrics['resolution_height']
                metrics['resolution_source'] = 'filename'
            else:
                metrics['resolution_width'] = 0
                metrics['resolution_height'] = 0
                metrics['resolution_pixels'] = 0
                metrics['resolution_source'] = 'none'
        
        # 2. Detect language codes using more generic approach
        # Look for language codes with various formats
        lang_match = re.search(r'[_-]([A-Z]{2,5})\b', filename)
        if lang_match:
            metrics['language_code'] = lang_match.group(1)
        elif any(suffix in filename for suffix in ['-EN', '_EN', '-en', '_en']):
            metrics['language_code'] = 'EN'
        else:
            metrics['language_code'] = None
        
        # 3. Detect quality indicators
        quality_patterns = [
            r'\b(HD)\b', r'\b(4K)\b', r'\b(UHD)\b', r'\b(HQ)\b', r'\b(LQ)\b',
            r'\b(high[\s_-]?quality)\b', r'\b(low[\s_-]?quality)\b',
            r'\b(high[\s_-]?res)\b', r'\b(low[\s_-]?res)\b',
            r'\b(1080p?)\b', r'\b(720p?)\b', r'\b(2160p?)\b', r'\b(480p?)\b'
        ]
        metrics['quality_indicators'] = []
        for pattern in quality_patterns:
            if re.search(pattern, filename, re.IGNORECASE):
                # Extract the matched quality indicator
                match = re.search(pattern, filename, re.IGNORECASE)
                if match:
                    metrics['quality_indicators'].append(match.group(1))
        
        # 4. Detect duplicate indicators
        duplicate_patterns = [
            r'\b(copy)\b', r'\((1|2|3)\)', r'[\s_-](1|2|3)[\s_.\)]',
            r'duplicate', r'backup', r'[(]?\s*copy\s*[)]?'
        ]
        metrics['duplicate_indicators'] = []
        for pattern in duplicate_patterns:
            if re.search(pattern, filename, re.IGNORECASE):
                match = re.search(pattern, filename, re.IGNORECASE)
                if match:
                    metrics['duplicate_indicators'].append(match.group(0))
        
        return metrics
    
    def score_files(self, file_info: List[dict]):
        """
        Apply scoring to files based on multiple extracted metrics.
        
        Args:
            file_info: List of file information dictionaries
        """
        # Get value ranges for normalization
        max_size = max([info['size'] for info in file_info]) if file_info else 0
        min_size = min([info['size'] for info in file_info]) if file_info else 0
        
        has_resolution_info = any(info['resolution_width'] > 0 for info in file_info)
        if has_resolution_info:
            max_resolution = max([info['resolution_pixels'] for info in file_info if info['resolution_pixels'] > 0])
        
        # Language preference scoring
        language_weights = {
            'EN': 100,  # English highest priority
            'US': 95,
            'UK': 90,
            'FR': 60,
            'DE': 60,
            'ES': 60,
            'IT': 60,
            'JP': 50,
            'KR': 50,
            'ZH': 45,
            'ZHS': 45,
            'ZHT': 45,
            None: 0   # No language code
        }
        
        # Process files
        for info in file_info:
            # Initialize factor-specific scores for better tracking
            info['size_score'] = 0
            info['resolution_score'] = 0
            info['language_score'] = 0
            info['quality_score'] = 0
            info['duplicate_score'] = 0
            
            # 1. Apply language preference scoring
            if info['language_code'] in language_weights:
                lang_score = language_weights[info['language_code']]
            else:
                # Default score for other language codes
                lang_score = 40
            
            info['language_score'] = lang_score
            info['score'] += lang_score
            print(f"  Language score: {lang_score} for {info['language_code']} in {os.path.basename(info['path'])}")
            
            # 2. Apply resolution scoring if available
            if has_resolution_info and info['resolution_pixels'] > 0:
                # Higher resolution gets higher score
                resolution_ratio = info['resolution_pixels'] / max_resolution
                resolution_score = resolution_ratio * 70  # High importance for resolution
                info['resolution_score'] = resolution_score
                info['score'] += resolution_score
                print(f"  Resolution score: {resolution_score:.1f} for {os.path.basename(info['path'])}")
            
            # 3. Apply size scoring - check if files have similar sizes
            size_range_percentage = ((max_size - min_size) / max_size) * 100 if max_size > 0 else 0
            
            # Calculate size ratio (0.0 to 1.0)
            size_ratio = info['size'] / max_size if max_size > 0 else 0
            
            # If all files are very similar in size, reduce the importance of size
            if size_range_percentage < 5:  # Within 5% size difference
                size_score = size_ratio * 15  # Low weight for size
            else:
                size_score = size_ratio * 40  # Medium weight for size
            
            info['size_score'] = size_score
            info['score'] += size_score
            print(f"  Size score: {size_score:.1f} for {os.path.basename(info['path'])}")
            
            # 4. Apply quality indicator scoring
            quality_score = 0
            if info['quality_indicators']:
                for indicator in info['quality_indicators']:
                    indicator_lower = indicator.lower()
                    # Higher quality indicators boost score
                    if any(term in indicator_lower for term in ['4k', 'uhd', '2160', 'high']):
                        quality_score += 40
                    elif any(term in indicator_lower for term in ['hd', '1080']):
                        quality_score += 30
                    elif any(term in indicator_lower for term in ['720']):
                        quality_score += 15
                    # Lower quality indicators reduce score
                    elif any(term in indicator_lower for term in ['low', '480', 'lq']):
                        quality_score -= 20
            
            info['quality_score'] = quality_score
            info['score'] += quality_score
            
            if quality_score != 0:
                print(f"  Quality score: {quality_score} for {os.path.basename(info['path'])}")
            
            # 5. Apply duplicate indicator penalties
            duplicate_penalty = 0
            if info['duplicate_indicators']:
                # Each duplicate indicator reduces score
                duplicate_penalty = -30 * len(info['duplicate_indicators'])
            
            info['duplicate_score'] = duplicate_penalty
            info['score'] += duplicate_penalty
            
            if duplicate_penalty != 0:
                print(f"  Duplicate penalty: {duplicate_penalty} for {os.path.basename(info['path'])}")
            
            # 6. Apply user preferences from PreferencesManager
            pref_manager = self.get_preferences_manager()
            if pref_manager:
                pref_score = 0
                for pref in pref_manager.get_patterns():
                    pattern = pref.pattern
                    if pattern in info['filename']:
                        # Apply preference
                        pref_score += pref.weight * 1.2
                        print(f"  Preference score: +{pref.weight * 1.2} for pattern '{pattern}' in {os.path.basename(info['path'])}")
                
                info['score'] += pref_score
            # If we have resolution information, prioritize that over raw file size
            # Use the correct resolution keys
            max_resolution = max([info['resolution_pixels'] for info in file_info if info['resolution_pixels'] > 0])
            
            for info in file_info:
                resolution_score = 0
                if info['resolution_width'] > 0:
                    # Calculate resolution ratio (0.0 to 1.0)
                    # No need to recalculate pixel count since we already have resolution_pixels
                    resolution_ratio = info['resolution_pixels'] / max_resolution
                    # Moderate weight for resolution: 0-50 points
                    resolution_score = resolution_ratio * 50
                
                # Still consider file size but with reduced weight
                size_ratio = info['size'] / max_size
                size_score = size_ratio * 20
                
                # Add both scores
                info['score'] += resolution_score + size_score
        else:
            # No resolution info available, use regular size-based scoring
            # Calculate percentage difference between smallest and largest file
            size_range_percentage = ((max_size - min_size) / max_size) * 100
            
            for info in file_info:
                # Calculate size ratio (0.0 to 1.0)
                size_ratio = info['size'] / max_size
                
                # For files that are very close in size (within 2.5%),
                # drastically reduce the importance of size differences
                if size_range_percentage < 2.5:
                    # Files are nearly identical in size, so size gets very little weight
                    size_points = size_ratio * 10
                else:
                    # Normal weight for size when there are significant differences
                    size_points = size_ratio * 50
                
                info['score'] += size_points
        
        # Load preference manager
        pref_manager = self.get_preferences_manager()
        
        # Score files based on filename patterns
        
        # 1. Penalty for duplicate patterns (files with duplicate indicators get lower scores)
        duplicate_patterns = [
            '(1)', '(2)', '(3)', '(copy)', 'copy', 'Copy',
            '_1', '_2', '_3', '-1', '-2', '-3', 'duplicate'
        ]
        
        for info in file_info:
            # Check for duplicate patterns in filename (lower score = more likely to be deleted)
            # Apply negative scoring for duplicate patterns
            for pattern in duplicate_patterns:
                if pattern in info['filename']:
                    # Reduce score by 30 points for each duplicate pattern found
                    info['score'] -= 30
        
        # 2. Bonus for preferred patterns from preferences
        if pref_manager:
            for info in file_info:
                for pref in pref_manager.get_patterns():
                    pattern = pref.pattern
                    # Handle special case for language codes
                    # Look for exact matches of "_EN", "_KR", etc.
                    if pattern.startswith("_") and f"{pattern}" in info['filename']:
                        # Give language code patterns higher weight when they match exactly
                        info['score'] += pref.weight * 1.8
                        print(f"  Applied preference weight {pref.weight * 1.8} for pattern '{pattern}' to {os.path.basename(info['path'])}")
                    elif pattern in info['filename']:
                        # Regular pattern match
                        info['score'] += pref.weight * 1.2
                        print(f"  Applied preference weight {pref.weight * 1.2} for pattern '{pattern}' to {os.path.basename(info['path'])}")
        
        # Print final scores before sorting
        print("\n--- Final Scores ---")
        for info in file_info:
            print(f"File: {os.path.basename(info['path'])}, Final Score: {info['score']}")
            
        # Sort by score (ascending, so lower scores come first)
        file_info.sort(key=lambda x: x['score'])
        
        # Print sorted order
        print("\n--- Sorted Order (lowest to highest score) ---")
        for i, info in enumerate(file_info):
            status = "KEEP" if i == len(file_info)-1 else "DELETE"
            print(f"{status}: {os.path.basename(info['path'])}, Score: {info['score']}")
        
        # Select all but the highest-scored file
        if len(file_info) > 1:
            # Always keep the highest-scored file
            files_to_delete = [info['path'] for info in file_info[:-1]]
            
            # Set checkboxes for files to delete (just checking boxes, not deleting)
            for path in files_to_delete:
                widget = self.image_widgets.get(path)
                if widget:
                    checkbox = widget.findChild(QCheckBox, f"checkbox_{path}")
                    if checkbox:
                        checkbox.setChecked(True)
    
    def show_preferences(self):
        """Show the preferences dialog."""
        dialog = PreferencesDialog(self)
        dialog.preferences_updated.connect(self.on_preferences_updated)
        dialog.exec()
    
    def on_preferences_updated(self):
        """Handle preferences being updated."""
        # Re-run auto-select with new preferences if checked
        if self.auto_select_checkbox.isChecked() and self.image_paths:
            self.auto_select_images()
    
    def open_selected_folder(self):
        """Open the folder containing the selected image(s)."""
        selected = self.get_selected_images()
        
        # If no images are selected, try to use any image in the current set
        if not selected and self.image_paths:
            selected = [self.image_paths[0]]
        
        if not selected:
            # No images to get folder from
            return
            
        # Handle multiple selected files from potentially different folders
        if len(selected) > 1:
            # Identify all unique folders
            folders = {os.path.dirname(path): path for path in selected}
            
            if len(folders) > 1:
                # Multiple different folders selected - count files per folder
                folder_counts = {}
                for path in selected:
                    folder = os.path.dirname(path)
                    folder_counts[folder] = folder_counts.get(folder, 0) + 1
                
                # Find the folder with the most selected files
                most_common_folder = max(folder_counts.items(), key=lambda x: x[1])[0]
                
                # Report if multiple folders were detected
                status_msg = f"Multiple folders detected. Opening the folder with most files: {os.path.basename(most_common_folder)}"
                
                # Update status
                if self.parent() and hasattr(self.parent(), 'progress_display'):
                    self.parent().progress_display.update_status(status_msg)
                
                folder = most_common_folder
            else:
                # All files are in the same folder
                folder = list(folders.keys())[0]
        else:
            # Only one file selected
            folder = os.path.dirname(selected[0])
        
        try:
            # Use the appropriate command based on the platform
            if os.name == 'nt':  # Windows
                os.startfile(folder)
            elif os.name == 'posix':  # Linux, Mac
                # For Linux, use xdg-open
                subprocess.Popen(['xdg-open', folder])
            
            # Update status via parent if available
            if self.parent() and hasattr(self.parent(), 'progress_display'):
                self.parent().progress_display.update_status(f"Opened folder: {folder}")
        except Exception as e:
            print(f"Error opening folder: {str(e)}")
            
            # Show error if possible
            if self.parent() and hasattr(self.parent(), 'progress_display'):
                self.parent().progress_display.update_status(f"Error opening folder: {str(e)}")
    
    def get_preferences_manager(self):
        """Get the preferences manager."""
        # Create a new instance each time for thread safety
        return PreferencesManager()
    
    def preload_next_sets(self, count: int = 3):
        """
        Preload images from the next few duplicate sets.
        This improves user experience when navigating between sets.
        
        Args:
            count: Number of future sets to preload
        """
        try:
            # Only if we have access to the duplicate sets
            if not hasattr(self.parent(), 'duplicate_list'):
                return
                
            duplicate_list = self.parent().duplicate_list
            if not hasattr(duplicate_list, 'duplicate_sets'):
                return
                
            # Get current index and duplicate sets
            current_hash = duplicate_list.current_hash
            if not current_hash:
                return
                
            duplicate_sets = duplicate_list.duplicate_sets
            if not duplicate_sets:
                return
                
            # Find next few sets
            keys = list(duplicate_sets.keys())
            if current_hash in keys:
                current_idx = keys.index(current_hash)
                
                # Preload the next few sets
                preload_paths = []
                for i in range(1, count + 1):
                    next_idx = (current_idx + i) % len(keys)
                    next_hash = keys[next_idx]
                    preload_paths.extend(duplicate_sets[next_hash])
                
                # Queue preloading with low priority
                if preload_paths:
                    self.image_loader.preload_images(
                        preload_paths,
                        self.thumbnail_size
                    )
        except Exception as e:
            # Don't let preloading errors affect the main functionality
            print(f"Error in preload_next_sets: {e}")
    def on_skip_clicked(self):
        """Handle skip button click by emitting the skip_requested signal."""
        # Emit the skip signal to notify that we want to skip this set
        self.skip_requested.emit()
    
    def on_delete_clicked(self):
        """Handle delete button click."""
        """Handle delete button click."""
        selected = self.get_selected_images()
        
        if selected:
            should_proceed = True
            
            # Only show confirmation if skip checkbox is not checked
            if not self.skip_confirm_checkbox.isChecked():
                # Show confirmation dialog
                msg_box = QMessageBox()
                msg_box.setIcon(QMessageBox.Warning)
                msg_box.setWindowTitle("Confirm Deletion")
                msg_box.setText(f"Are you sure you want to move {len(selected)} image(s) to trash?")
                msg_box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
                msg_box.setDefaultButton(QMessageBox.No)
                
                if msg_box.exec() != QMessageBox.Yes:
                    should_proceed = False
            
            if should_proceed:
                # Emit signal with selected image paths
                self.delete_requested.emit(selected)
        else:
            # Show warning if no images selected
            QMessageBox.information(
                self, "No Selection", "Please select at least one image to delete."
            )