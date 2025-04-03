"""
Progress display widget for showing task progress and allowing cancellation.
"""
from PySide6.QtCore import Slot, Signal
from PySide6.QtWidgets import (
    QWidget, QProgressBar, QLabel, QVBoxLayout,
    QPushButton, QHBoxLayout
)

class ProgressDisplay(QWidget):
    """
    Widget that displays progress information for ongoing tasks.
    Includes a progress bar, status text label, and a cancel button.
    """
    # Signal emitted when user clicks cancel button
    cancelled = Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Initialize UI components
        self.init_ui()
        
    def init_ui(self):
        """Initialize the user interface components."""
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 10, 0, 10)
        
        # Status label
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("font-weight: bold;")
        main_layout.addWidget(self.status_label)
        
        # Control layout (progress bar and cancel button)
        control_layout = QHBoxLayout()
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        control_layout.addWidget(self.progress_bar, 5)  # Give progress bar more space
        
        # Cancel button
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setEnabled(False)  # Disabled by default
        self.cancel_button.clicked.connect(self.on_cancel_clicked)
        control_layout.addWidget(self.cancel_button, 1)
        
        # Add control layout to main layout
        main_layout.addLayout(control_layout)
        
        # Detail label (for additional information)
        self.detail_label = QLabel("")
        main_layout.addWidget(self.detail_label)
        
        # Set layout
        self.setLayout(main_layout)
    
    @Slot(int, int)    
    @Slot(int)
    def update_progress(self, value, maximum=None):
        """
        Update the progress bar value.
        
        Args:
            value: Current progress value
            maximum: Optional new maximum value
        """
        if maximum is not None:
            self.progress_bar.setMaximum(maximum)
        
        self.progress_bar.setValue(value)
    
    @Slot(str)
    def update_status(self, text):
        """
        Update the status text.
        
        Args:
            text: New status text
        """
        self.status_label.setText(text)
    
    @Slot(str)
    def update_detail(self, text):
        """
        Update the detail text.
        
        Args:
            text: New detail text
        """
        self.detail_label.setText(text)
    
    @Slot()
    def reset(self):
        """Reset the progress display to initial state."""
        self.progress_bar.setValue(0)
        self.status_label.setText("Ready")
        self.detail_label.setText("")
        self.cancel_button.setEnabled(False)
        
    def set_operation_in_progress(self, in_progress):
        """
        Enable or disable the cancel button based on whether an operation is in progress.
        
        Args:
            in_progress: True if an operation is in progress, False otherwise
        """
        self.cancel_button.setEnabled(in_progress)
    
    def on_cancel_clicked(self):
        """Handle the cancel button click event."""
        self.cancel_button.setEnabled(False)
        self.update_status("Cancelling operation...")
        # Emit the cancelled signal for MainWindow to handle
        self.cancelled.emit()