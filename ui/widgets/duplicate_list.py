"""
Duplicate list widget for displaying sets of duplicate images.
"""
import os
import time
from typing import Dict, List, Optional, Set, Tuple, Iterator

from PySide6.QtCore import Qt, Signal, Slot, QTimer, QSize
from PySide6.QtWidgets import (
    QWidget, QTreeWidget, QTreeWidgetItem, QVBoxLayout,
    QLabel, QHBoxLayout, QPushButton, QScrollBar,
    QApplication, QAbstractItemView, QProgressBar
)

class DuplicateList(QWidget):
    """
    Widget that displays sets of duplicate images in a tree structure.
    
    Signals:
        set_selected: Emitted when a duplicate set is selected with a list of image paths
    """
    # Signal emitted when a duplicate set is selected
    set_selected = Signal(list)
    # Signal emitted when loading is complete
    loading_complete = Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.duplicate_sets = {}  # Dictionary of hash: [image_paths]
        self.current_hash = None  # Currently selected hash
        self.loaded_items = set()  # Set of hashes that have been fully loaded
        self.is_loading = False  # Flag to track if we're currently loading items
        self.chunk_size = 10  # Number of sets to load at once
        self.update_timer = None  # Timer for chunked updates
        self.scrollbar_value = 0  # Track scrollbar position
        self.metadata_cache = {}  # Cache for file metadata (size, dimensions)
        
        self.init_ui()
    
    def init_ui(self):
        """Initialize the user interface components."""
        # Main layout
        main_layout = QVBoxLayout(self)
        
        # Header section
        header_layout = QHBoxLayout()
        
        # Title label
        title_label = QLabel("Duplicate Image Sets")
        title_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        header_layout.addWidget(title_label)
        
        # Spacer to push counter to right
        header_layout.addStretch()
        
        # Counter label
        self.counter_label = QLabel("0 sets found")
        header_layout.addWidget(self.counter_label)
        
        main_layout.addLayout(header_layout)
        
        # Progress bar for loading
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        main_layout.addWidget(self.progress_bar)
        
        # Tree widget for displaying the duplicate sets
        self.tree_widget = QTreeWidget()
        self.tree_widget.setHeaderLabels(["Duplicate Sets", "Size", "Dimensions"])
        self.tree_widget.setColumnWidth(0, 400)  # Width for file path column
        self.tree_widget.setAlternatingRowColors(True)
        self.tree_widget.itemSelectionChanged.connect(self.on_selection_changed)
        # Connect the itemExpanded signal internally to prepare for lazy loading
        self.tree_widget.itemExpanded.connect(self._load_children)
        
        # Set item delegate for more control over rendering
        self.tree_widget.setUniformRowHeights(True)  # Better performance with large lists
        self.tree_widget.setSortingEnabled(True)  # Enable sorting
        self.tree_widget.sortByColumn(0, Qt.AscendingOrder)  # Default sort
        
        # Connect scroll event for lazy loading
        self.tree_widget.verticalScrollBar().valueChanged.connect(self.on_scroll)
        self.tree_widget.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)  # Smoother scrolling
        
        main_layout.addWidget(self.tree_widget)
        
        # Button layout
        button_layout = QHBoxLayout()
        
        # Expand all button
        expand_button = QPushButton("Expand All")
        expand_button.clicked.connect(self.tree_widget.expandAll)
        button_layout.addWidget(expand_button)
        
        # Collapse all button
        collapse_button = QPushButton("Collapse All")
        collapse_button.clicked.connect(self.tree_widget.collapseAll)
        button_layout.addWidget(collapse_button)
        
        # Refresh button
        refresh_button = QPushButton("Refresh")
        refresh_button.clicked.connect(self.refresh)
        button_layout.addWidget(refresh_button)
        
        main_layout.addLayout(button_layout)
        
        # Set layout
        self.setLayout(main_layout)
    
    @Slot(dict)
    def update_duplicate_sets(self, duplicate_sets: Dict[str, List[str]]):
        """
        Update the tree widget with new duplicate sets using chunked loading.
        
        Args:
            duplicate_sets: Dictionary mapping hash values to lists of image paths
        """
        # Stop any previous loading
        if self.update_timer and self.update_timer.isActive():
            self.update_timer.stop()
        
        # Store the new sets
        self.duplicate_sets = duplicate_sets
        self.loaded_items.clear()
        self.is_loading = True
        
        # Clear current items
        self.tree_widget.clear()
        
        # Update counter label
        set_count = len(self.duplicate_sets)
        self.counter_label.setText(f"{set_count} sets found (loading...)")
        
        # Show progress bar
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(set_count > self.chunk_size)
        
        # Start chunked loading if there are lots of items
        if set_count > self.chunk_size:
            self._load_chunks()
        else:
            # For small sets, just load everything at once
            self._load_all_items()
    
    def _load_chunks(self):
        """Load duplicate sets in chunks to prevent UI freezing."""
        self.is_loading = True
        
        # Create a timer to load chunks with delay
        if not self.update_timer:
            self.update_timer = QTimer(self)
            self.update_timer.timeout.connect(self._load_next_chunk)
        
        # Start the timer
        self.update_timer.start(10)  # 10ms between chunks
    
    def _load_next_chunk(self):
        """Load the next chunk of duplicate sets."""
        # Calculate progress
        total_sets = len(self.duplicate_sets)
        loaded_sets = len(self.loaded_items)
        progress = int((loaded_sets / total_sets) * 100) if total_sets > 0 else 100
        
        # Update progress bar
        self.progress_bar.setValue(progress)
        
        # Get items to load in this chunk
        items_to_load = self._get_next_chunk()
        
        # Stop if no more items to load
        if not items_to_load:
            self._finish_loading()
            return
        
        # Load this chunk of items
        for hash_value in items_to_load:
            self._create_parent_item(hash_value)
            self.loaded_items.add(hash_value)
            
            # Process events to keep UI responsive
            QApplication.processEvents()
        
        # Update counter label with loading progress
        self.counter_label.setText(f"{total_sets} sets found (loading {loaded_sets}/{total_sets})")
    
    def _get_next_chunk(self) -> List[str]:
        """Get the next chunk of hash values to load."""
        # Get all hash values that haven't been loaded yet
        remaining = [h for h in self.duplicate_sets.keys() if h not in self.loaded_items]
        
        # Priority loading for visible items
        visible_rect = self.tree_widget.viewport().rect()
        
        # Get items that would be visible first
        # For simplicity, we'll just take the next chunk based on current count
        return remaining[:self.chunk_size]
    
    def _load_all_items(self):
        """Load all items at once (for small datasets)."""
        # Show all sets
        for hash_value in self.duplicate_sets.keys():
            self._create_parent_item(hash_value)
            self.loaded_items.add(hash_value)
        
        self._finish_loading()
    
    def _finish_loading(self):
        """Finish the loading process."""
        if self.update_timer:
            self.update_timer.stop()
        
        self.is_loading = False
        self.progress_bar.setVisible(False)
        
        # Update counter label
        set_count = len(self.duplicate_sets)
        self.counter_label.setText(f"{set_count} sets found")
        
        # Emit the loading complete signal
        self.loading_complete.emit()
    
    def _create_parent_item(self, hash_value: str):
        """Create a tree item for a duplicate set."""
        paths = self.duplicate_sets.get(hash_value, [])
        
        if len(paths) > 1:  # Only show sets with at least 2 duplicates
            # Create parent item for this set
            set_item = QTreeWidgetItem(self.tree_widget)
            
            # Get a representative filename from the first image in the set
            if paths:
                representative_path = paths[0]
                filename = os.path.basename(representative_path)
                # Use the filename as part of the set label
                set_item.setText(0, f"{filename} ({len(paths)} duplicates)")
            else:
                set_item.setText(0, f"Duplicate Set ({len(paths)} files)")
            
            # Store the hash value as data for easy access later
            set_item.setData(0, Qt.UserRole, hash_value)
            set_item.setFlags(set_item.flags() | Qt.ItemIsAutoTristate)
            
            # Store a flag indicating children aren't loaded yet
            set_item.setData(0, Qt.UserRole + 1, False)
            
            # We don't load child items until the parent is expanded
            set_item.setChildIndicatorPolicy(QTreeWidgetItem.ShowIndicator)
    
    def _load_children(self, parent_item: QTreeWidgetItem):
        """Lazily load children for a parent item when expanded."""
        # Check if children are already loaded
        if parent_item.data(0, Qt.UserRole + 1):
            return
            
        # Get hash value and paths
        hash_value = parent_item.data(0, Qt.UserRole)
        paths = self.duplicate_sets.get(hash_value, [])
        
        # Add child items for each image in the set
        for path in paths:
            child_item = QTreeWidgetItem(parent_item)
            child_item.setText(0, path)
            
            # Lazy load metadata (size, dimensions) in background
            self._queue_metadata_load(child_item, path)
        
        # Mark as loaded
        parent_item.setData(0, Qt.UserRole + 1, True)
    
    def _queue_metadata_load(self, item: QTreeWidgetItem, path: str):
        """Queue loading metadata for an item."""
        # Check cache first
        if path in self.metadata_cache:
            size_str, dimensions = self.metadata_cache[path]
            item.setText(1, size_str)
            item.setText(2, dimensions)
            return
            
        # Set placeholder text
        item.setText(1, "Loading...")
        item.setText(2, "Loading...")
        
        # In a real implementation, we'd load this in a background thread
        # For simplicity, we'll just load it directly here
        try:
            file_size = os.path.getsize(path)
            size_kb = file_size / 1024
            size_mb = size_kb / 1024
            
            if size_mb >= 1:
                size_str = f"{size_mb:.2f} MB"
            else:
                size_str = f"{size_kb:.2f} KB"
            
            # For dimensions, we'd use PIL/QImage but that's expensive
            # So we'll just use a placeholder for now
            dimensions = "Unknown"
            
            # Update cache
            self.metadata_cache[path] = (size_str, dimensions)
            
            # Update item
            item.setText(1, size_str)
            item.setText(2, dimensions)
            
        except Exception as e:
            item.setText(1, "Error")
            item.setText(2, "Error")
    
    def refresh(self):
        """Refresh the tree widget display with current duplicate sets."""
        # Clear loaded items tracking
        self.loaded_items.clear()
        
        # Reload using chunked loading
        if len(self.duplicate_sets) > self.chunk_size:
            self._load_chunks()
        else:
            self._load_all_items()
    
    def on_selection_changed(self):
        """Handle selection change in the tree widget."""
        # Get selected items
        selected_items = self.tree_widget.selectedItems()
        
        if selected_items:
            # Check if the selection is a parent item (duplicate set)
            parent_item = selected_items[0]
            
            # If this is a child item, get its parent
            if parent_item.parent():
                parent_item = parent_item.parent()
            
            # Ensure children are loaded
            if not parent_item.data(0, Qt.UserRole + 1):
                self._load_children(parent_item)
            
            # Store current hash
            self.current_hash = parent_item.data(0, Qt.UserRole)
            
            # Collect all the paths in this duplicate set
            paths = []
            for i in range(parent_item.childCount()):
                child = parent_item.child(i)
                paths.append(child.text(0))
            
            # Emit signal with the image paths in this set
            if paths:
                self.set_selected.emit(paths)
    
    def clear(self):
        """Clear all duplicate sets."""
        self.duplicate_sets = {}
        self.tree_widget.clear()
        self.counter_label.setText("0 sets found")
    
    def select_next_set(self) -> bool:
        """
        Select the next duplicate set in the tree.
        If the last set is currently selected, it will loop back to the first set.
        
        Returns:
            True if successfully selected a set, False if no sets available
        """
        # Get the root items (duplicate sets)
        root_count = self.tree_widget.topLevelItemCount()
        
        if root_count == 0:
            return False
        
        # Find the currently selected item
        selected_items = self.tree_widget.selectedItems()
        
        # Determine the next index to select
        next_index = 0
        if selected_items:
            current_item = selected_items[0]
            
            # If it's a child item, get its parent
            if current_item.parent():
                current_item = current_item.parent()
            
            # Find the index of the current item
            for i in range(root_count):
                if self.tree_widget.topLevelItem(i) == current_item:
                    next_index = (i + 1) % root_count
                    break
        
        # Select the next item
        next_item = self.tree_widget.topLevelItem(next_index)
        if next_item:
            # Clear current selection
            self.tree_widget.clearSelection()
            
            # Select the next item
            next_item.setSelected(True)
            
            # Make sure the item is visible
            self.tree_widget.scrollToItem(next_item)
            
            return True
        
        return False
    
    def on_scroll(self, value):
        """Handle scrollbar value change."""
        # Track scrollbar position
        old_value = self.scrollbar_value
        self.scrollbar_value = value
        
        # Only load items when scrolling down to conserve resources
        if value > old_value:
            # Find visible items
            visible_items = self._get_visible_items()
            
            # Load children for visible parent items if needed
            for item in visible_items:
                if not item.parent() and not item.data(0, Qt.UserRole + 1):
                    self._load_children(item)
    
    def _get_visible_items(self) -> List[QTreeWidgetItem]:
        """Get tree items that are currently visible in the viewport."""
        result = []
        
        # Get viewport rectangle
        viewport = self.tree_widget.viewport()
        viewport_rect = viewport.rect()
        
        # Check all top-level items
        for i in range(self.tree_widget.topLevelItemCount()):
            item = self.tree_widget.topLevelItem(i)
            rect = self.tree_widget.visualItemRect(item)
            
            # If the item is visible in the viewport
            if rect.intersects(viewport_rect):
                result.append(item)
                
                # If expanded, check visible children too
                if item.isExpanded():
                    for j in range(item.childCount()):
                        child = item.child(j)
                        child_rect = self.tree_widget.visualItemRect(child)
                        if child_rect.intersects(viewport_rect):
                            result.append(child)
        
        return result