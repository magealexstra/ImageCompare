"""
Main window module for the ImageCompare application.
"""
import os
import threading
from typing import Dict, List

from PySide6.QtCore import Qt, Slot, Signal, QObject, QEvent
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QMessageBox, QApplication, QStatusBar, QLabel,
    QTreeWidgetItem
)

from core.scanner import find_image_files
from core.hasher import calculate_perceptual_hash
from core.duplicate_finder import identify_duplicates, find_duplicates
from core.file_handler import move_to_trash
from core.resource_manager import get_resource_manager

from ui.widgets.directory_selector import DirectorySelector
from ui.widgets.progress_display import ProgressDisplay
from ui.widgets.duplicate_list import DuplicateList
from ui.widgets.image_compare import ImageCompare

# Helper class for thread-safe signals
class ThreadHelper(QObject):
    """Helper class to emit signals from a worker thread to the main thread."""
    update_status_signal = Signal(str)
    update_progress_signal = Signal(int)
    update_duplicate_sets_signal = Signal(dict)
    enable_scan_button_signal = Signal()

class MainWindow(QMainWindow):
    """Main window for the ImageCompare application."""
    
    def __init__(self):
        super().__init__()
        
        # Instance variables and worker threads
        self.image_files = []
        self.duplicate_groups = {}
        self.scanning_thread = None
        self.cancel_requested = False
        self.select_next_after_loading = False  # Flag to select next set after loading
        
        # Initialize resource manager
        self.resource_manager = get_resource_manager()
        self.resource_manager.start_monitoring()
        
        # Track whether application is shutting down
        self.shutting_down = False
        
        # Create thread helper
        self.thread_helper = ThreadHelper()
        
        # Set up the user interface
        self.init_ui()
        
        # Connect signals
        self.connect_signals()
        
    def init_ui(self):
        """Initialize the user interface."""
        # Set window properties
        self.setWindowTitle("ImageCompare - Find and Delete Duplicate Images")
        self.resize(1200, 800)
        
        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        main_layout = QVBoxLayout(central_widget)
        
        # Create progress display widget at the top
        self.progress_display = ProgressDisplay()
        main_layout.addWidget(self.progress_display)
        
        # Create main vertical splitter (top: image comparison, bottom: duplicate list and directory selector)
        main_splitter = QSplitter(Qt.Vertical)
        
        # Create image compare widget for the top section
        # Pass self so it can access progress_display for status messages
        self.image_compare = ImageCompare(self)
        main_splitter.addWidget(self.image_compare)
        
        # Create bottom horizontal splitter for duplicate list and directory selector
        bottom_splitter = QSplitter(Qt.Horizontal)
        
        # Create duplicate list widget for the left side
        self.duplicate_list = DuplicateList()
        bottom_splitter.addWidget(self.duplicate_list)
        
        # Create directory selector widget for the right side
        self.directory_selector = DirectorySelector()
        bottom_splitter.addWidget(self.directory_selector)
        
        # Set initial splitter sizes for bottom section (50% left, 50% right)
        bottom_splitter.setSizes([500, 500])
        
        # Add bottom splitter to main vertical splitter
        main_splitter.addWidget(bottom_splitter)
        
        # Set initial splitter sizes for main splitter (70% top, 30% bottom)
        main_splitter.setSizes([700, 300])
        
        # Add main splitter to layout
        main_layout.addWidget(main_splitter)
        
        # Add resource usage monitoring to the UI
        self.setup_resource_monitoring()
        
        # Set central widget layout
        central_widget.setLayout(main_layout)
        
        # Register for application quit events to clean up resources
        app = QApplication.instance()
        if app:
            app.aboutToQuit.connect(self.cleanup_resources)
    
    def setup_resource_monitoring(self):
        """Set up resource monitoring display and callbacks."""
        # Create a status bar if not already present
        if not self.statusBar():
            self.setStatusBar(QStatusBar())
            
        # Create permanent status bar widgets
        self.cpu_label = QLabel("CPU: 0%")
        self.memory_label = QLabel("Memory: 0%")
        
        # Add to status bar
        self.statusBar().addPermanentWidget(self.cpu_label)
        self.statusBar().addPermanentWidget(self.memory_label)
        
        # Register callback with resource manager
        self.resource_manager.register_monitoring_callback(self.update_resource_display)
    
    def update_resource_display(self, cpu_percent, memory_percent):
        """Update the resource display with current CPU and memory usage."""
        self.cpu_label.setText(f"CPU: {cpu_percent:.1f}%")
        self.memory_label.setText(f"Memory: {memory_percent:.1f}%")
        
        # Change color based on load
        if cpu_percent > 80:
            self.cpu_label.setStyleSheet("color: red; font-weight: bold")
        elif cpu_percent > 60:
            self.cpu_label.setStyleSheet("color: orange")
        else:
            self.cpu_label.setStyleSheet("")
            
        if memory_percent > 80:
            self.memory_label.setStyleSheet("color: red; font-weight: bold")
        elif memory_percent > 60:
            self.memory_label.setStyleSheet("color: orange")
        else:
            self.memory_label.setStyleSheet("")
    
    def connect_signals(self):
        """Connect widget signals to slots."""
        # Connect directory selector's scan signal
        self.directory_selector.directories_selected.connect(self.start_scanning)
        
        # Connect duplicate list's selection signal
        self.duplicate_list.set_selected.connect(self.image_compare.set_images)
        
        # Connect duplicate list's tree expansion signal
        self.duplicate_list.tree_widget.itemExpanded.connect(self.on_tree_item_expanded)
        
        # Connect duplicate list's loading complete signal
        self.duplicate_list.loading_complete.connect(self.on_duplicate_list_loaded)
        
        # Connect image compare's delete and skip signals
        self.image_compare.delete_requested.connect(self.delete_images)
        self.image_compare.skip_requested.connect(self.skip_duplicate_set)
        # Connect thread helper signals
        self.thread_helper.update_status_signal.connect(self.progress_display.update_status)
        self.thread_helper.update_progress_signal.connect(self.progress_display.update_progress)
        self.thread_helper.update_duplicate_sets_signal.connect(self.duplicate_list.update_duplicate_sets)
        self.thread_helper.enable_scan_button_signal.connect(self.enable_scan_button)
        
        # Connect progress display's cancel signal
        self.progress_display.cancelled.connect(self.cancel_scanning)
        self.thread_helper.enable_scan_button_signal.connect(self.enable_scan_button)
    
    @Slot(list)
    def start_scanning(self, directories: List[str]):
        """
        Start the scanning process in a separate thread.
        
        Args:
            directories: List of directories to scan
        """
        # Disable scan button to prevent multiple scans
        self.directory_selector.scan_button.setEnabled(False)
        
        # Clear previous results
        self.duplicate_list.clear()
        self.image_compare.clear_images()
        
        # Reset progress display and enable cancel button
        self.progress_display.reset()
        self.progress_display.set_operation_in_progress(True)
        self.progress_display.update_status("Initializing scan...")
        
        # Reset cancellation flag
        self.cancel_requested = False
        
        # Start scanning thread
        self.scanning_thread = threading.Thread(
            target=self.scanning_process,
            args=(directories,)
        )
        self.scanning_thread.daemon = True
        self.scanning_thread.start()
    
    def scanning_process(self, directories: List[str]):
        """
        Process to scan directories and find duplicates.
        This runs in a separate thread to avoid blocking the UI.
        Uses parallel processing for improved performance.
        Supports cancellation.
        
        Args:
            directories: List of directories to scan
        """
        try:
            # Step 1: Find all image files using parallel processing
            self.update_progress_status("Scanning for image files in parallel...", 0)
            
            # Check for cancellation
            if self.cancel_requested:
                self.handle_cancellation()
                return
                
            self.image_files = find_image_files(directories)
            
            self.update_progress_status(
                f"Found {len(self.image_files)} image files", 10
            )
            
            if not self.image_files:
                self.update_progress_status("No image files found!", 0)
                self.thread_helper.enable_scan_button_signal.emit()
                return
            
            # Check for cancellation
            if self.cancel_requested:
                self.handle_cancellation()
                return
                
            # Step 2: Calculate hashes for all images in parallel
            self.update_progress_status("Calculating image hashes using multi-core processing...", 10)
            
            # Track current progress for hash calculation
            total_files = len(self.image_files)
            
            # Define progress callback for hash calculation
            def hash_progress_callback(processed_count, total_count):
                # Check for cancellation during processing
                if self.cancel_requested:
                    raise InterruptedError("Operation cancelled by user")
                    
                progress = 10 + int((processed_count / total_count) * 70)
                self.update_progress_status(
                    f"Hashing images: {processed_count}/{total_count}", progress
                )
            
            # Step 3: Find duplicates in parallel (combines hash calculation and identification)
            self.duplicate_groups = find_duplicates(
                self.image_files,
                progress_callback=hash_progress_callback
            )
            
            # Check for cancellation
            if self.cancel_requested:
                self.handle_cancellation()
                return
                
            # Step 4: Update the UI with results
            duplicate_count = len(self.duplicate_groups)
            duplicate_file_count = sum(len(paths) for paths in self.duplicate_groups.values())
            
            self.update_progress_status(
                f"Found {duplicate_count} duplicate sets with {duplicate_file_count} total files", 100
            )
            
            # Update duplicate list
            self.thread_helper.update_duplicate_sets_signal.emit(self.duplicate_groups)
            
        except InterruptedError:
            # Handle cancellation exception
            self.handle_cancellation()
            return
        except Exception as e:
            # Handle any exceptions
            error_message = f"Error during scanning: {str(e)}"
            self.update_progress_status(error_message, 0)
            # We can't directly call QMessageBox from a non-GUI thread
            print(error_message)
        
        finally:
            # Re-enable scan button
            self.thread_helper.enable_scan_button_signal.emit()
            # Disable cancel button as operation is complete
            self.progress_display.set_operation_in_progress(False)
    
    def update_progress_status(self, status_text, progress_value):
        """
        Update the progress display from a non-UI thread.
        
        Args:
            status_text: Status message to display
            progress_value: Progress bar value (0-100)
        """
        # Emit signals to safely update UI from another thread
        self.thread_helper.update_status_signal.emit(status_text)
        self.thread_helper.update_progress_signal.emit(progress_value)
    
    @Slot(QTreeWidgetItem)
    def on_tree_item_expanded(self, item):
        """Handle tree item expansion to trigger lazy loading."""
        # Delegate to the duplicate list to load children
        if hasattr(self.duplicate_list, '_load_children'):
            self.duplicate_list._load_children(item)
    
    def cleanup_resources(self):
        """Clean up resources before application exit."""
        self.shutting_down = True
        
        # Stop resource monitoring
        if hasattr(self, 'resource_manager'):
            self.resource_manager.stop_monitoring()
        
        # Stop any running scan thread
        self.cancel_requested = True
        
        # Clean up image loader in the ImageCompare widget
        if hasattr(self.image_compare, 'image_loader'):
            self.image_compare.image_loader.shutdown()
            
        # Wait for scanning thread to finish
        if self.scanning_thread and self.scanning_thread.is_alive():
            self.scanning_thread.join(timeout=0.5)
    
    @Slot()
    @Slot()
    def cancel_scanning(self):
        """Handle cancellation request from the progress display."""
        self.cancel_requested = True
        self.update_progress_status("Cancellation requested, waiting for operations to complete...", -1)
    
    def handle_cancellation(self):
        """Clean up after cancellation."""
        self.update_progress_status("Operation cancelled by user", 0)
        self.thread_helper.enable_scan_button_signal.emit()
        self.progress_display.set_operation_in_progress(False)
    
    @Slot()
    def enable_scan_button(self):
        """Re-enable the scan button."""
        self.directory_selector.scan_button.setEnabled(True)
    
    @Slot()
    def on_duplicate_list_loaded(self):
        """Handle completion of duplicate list loading."""
        # If we need to select the next set after loading
        if self.select_next_after_loading:
            # Reset the flag
            self.select_next_after_loading = False
            
            # Try to select the next set
            if not self.duplicate_list.select_next_set():
                # If couldn't select next (shouldn't happen), show message
                self.progress_display.update_status("Processing complete. Please select a duplicate set.")
    
    @Slot()
    def skip_duplicate_set(self):
        """
        Skip the current duplicate set without deleting any files.
        Removes the current set from the duplicate groups and selects the next set.
        """
        # Find the current hash from the duplicate list
        current_hash = self.duplicate_list.current_hash
        
        if current_hash and current_hash in self.duplicate_groups:
            # Remove this set from the duplicate groups
            del self.duplicate_groups[current_hash]
            
            # Display status message
            self.progress_display.update_status("Skipped duplicate set. Moving to next set...")
            
            # Check if there are any duplicate groups left
            if self.duplicate_groups:
                # Still have duplicates, update the UI
                # Set the flag to select next set after loading completes
                self.select_next_after_loading = True
                self.duplicate_list.update_duplicate_sets(self.duplicate_groups)
            else:
                # No more duplicates, clear everything and show message
                self.duplicate_list.clear()
                self.image_compare.clear_images()
                self.progress_display.update_status("All duplicate sets have been reviewed!")
    
    @Slot(list)
    def delete_images(self, image_paths: List[str]):
        """
        Delete selected images.
        
        Args:
            image_paths: List of paths to images to delete
        """
        try:
            # Move files to trash
            moved_files = move_to_trash(image_paths)
            
            if moved_files:
                # Show success message as a status update (non-modal)
                self.progress_display.update_status(f"Successfully moved {len(moved_files)} file(s) to trash.")
                
                # Update the duplicate groups
                self.update_duplicate_groups_after_deletion(moved_files)
                
                # Check if there are any duplicate groups left
                if self.duplicate_groups:
                    # Still have duplicates, update the UI
                    # Set the flag to select next set after loading completes
                    self.select_next_after_loading = True
                    self.duplicate_list.update_duplicate_sets(self.duplicate_groups)
                else:
                    # No more duplicates, clear everything and show message
                    self.duplicate_list.clear()
                    self.image_compare.clear_images()
                    self.progress_display.update_status("All duplicates have been resolved!")
            else:
                # Show failure as status update instead of dialog
                self.progress_display.update_status("No files were moved to trash.")
                
        except Exception as e:
            # Show error as status update instead of dialog
            self.progress_display.update_status(f"Error during deletion: {str(e)}")
    
    def update_duplicate_groups_after_deletion(self, deleted_files: List[str]):
        """
        Update duplicate groups after files have been deleted.
        
        Args:
            deleted_files: List of paths to deleted files
        """
        # Create a new duplicate groups dictionary
        updated_groups = {}
        
        # For each hash group
        for hash_value, paths in self.duplicate_groups.items():
            # Filter out deleted files
            updated_paths = [path for path in paths if path not in deleted_files]
            
            # Only keep groups with at least 2 files (duplicates)
            if len(updated_paths) > 1:
                updated_groups[hash_value] = updated_paths
        
        # Update the class variable
        self.duplicate_groups = updated_groups