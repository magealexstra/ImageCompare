"""
Preferences dialog for configuring auto-select pattern preferences.
"""
import json
import os
from typing import Dict, List, Tuple

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
    QPushButton, QSlider, QListWidget, QListWidgetItem, 
    QWidget, QMessageBox, QGridLayout, QFrame
)

class PatternPreference:
    """Class representing a pattern preference for auto-select."""
    def __init__(self, pattern: str, weight: int = 20):
        self.pattern = pattern
        self.weight = weight  # 10-30

class PreferencesManager:
    """Manager for handling pattern preferences."""
    
    CONFIG_PATH = os.path.expanduser("~/.imagecompare_prefs.json")
    
    def __init__(self):
        self.patterns = []  # List of PatternPreference objects
        self.load_preferences()
    
    def add_pattern(self, pattern: str, weight: int = 20) -> PatternPreference:
        """Add a new pattern preference."""
        # Don't add duplicate patterns
        for pref in self.patterns:
            if pref.pattern == pattern:
                pref.weight = weight
                return pref
                
        pref = PatternPreference(pattern, weight)
        self.patterns.append(pref)
        return pref
    
    def remove_pattern(self, pattern: str) -> bool:
        """Remove a pattern preference."""
        for i, pref in enumerate(self.patterns):
            if pref.pattern == pattern:
                self.patterns.pop(i)
                return True
        return False
    
    def get_patterns(self) -> List[PatternPreference]:
        """Get all pattern preferences."""
        return self.patterns
    
    def save_preferences(self):
        """Save preferences to file."""
        data = {
            "patterns": [{"pattern": p.pattern, "weight": p.weight} for p in self.patterns]
        }
        
        try:
            with open(self.CONFIG_PATH, 'w') as f:
                json.dump(data, f, indent=2)
            return True
        except Exception as e:
            print(f"Error saving preferences: {str(e)}")
            return False
    
    def load_preferences(self):
        """Load preferences from file."""
        if not os.path.exists(self.CONFIG_PATH):
            # Create default preferences if file doesn't exist
            self.patterns = [
                PatternPreference("_EN", 40),  # Increase weight and match exact format in filenames
                PatternPreference("EN", 35),   # Also include without underscore
                PatternPreference("HD", 25),
                PatternPreference("4K", 28)
            ]
            self.save_preferences()
            return
        
        try:
            with open(self.CONFIG_PATH, 'r') as f:
                data = json.load(f)
                
            self.patterns = []
            for p in data.get("patterns", []):
                self.add_pattern(p.get("pattern", ""), p.get("weight", 20))
        except Exception as e:
            print(f"Error loading preferences: {str(e)}")
            # Use defaults if loading fails
            self.patterns = [
                PatternPreference("_EN", 40),  # Increase weight and match exact format in filenames
                PatternPreference("EN", 35),   # Also include without underscore
                PatternPreference("HD", 25),
                PatternPreference("4K", 28)
            ]

class PatternItemWidget(QWidget):
    """Custom widget for displaying a pattern preference in the list."""
    
    def __init__(self, pattern: str, weight: int, parent=None):
        super().__init__(parent)
        
        # Layout
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Pattern label
        self.pattern_label = QLabel(pattern)
        layout.addWidget(self.pattern_label)
        
        layout.addStretch()
        
        # Weight label
        self.weight_label = QLabel(f"Weight: {weight}")
        layout.addWidget(self.weight_label)
        
        self.setLayout(layout)

class PreferencesDialog(QDialog):
    """Dialog for configuring pattern preferences for auto-select."""
    
    preferences_updated = Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.pref_manager = PreferencesManager()
        self.init_ui()
        self.load_patterns()
    
    def init_ui(self):
        """Initialize the user interface."""
        self.setWindowTitle("Pattern Preferences")
        self.setMinimumWidth(450)
        self.setMinimumHeight(400)
        
        # Main layout
        main_layout = QVBoxLayout(self)
        
        # Instructions
        instructions = QLabel(
            "Configure patterns to prioritize in auto-select. Higher weights (10-30) "
            "mean files containing these patterns will be more likely to be kept."
        )
        instructions.setWordWrap(True)
        main_layout.addWidget(instructions)
        
        # Separator
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        main_layout.addWidget(line)
        
        # Patterns list
        self.patterns_list = QListWidget()
        main_layout.addWidget(self.patterns_list)
        
        # Add pattern controls
        add_layout = QGridLayout()
        
        # Pattern input
        add_layout.addWidget(QLabel("Pattern:"), 0, 0)
        self.pattern_input = QLineEdit()
        add_layout.addWidget(self.pattern_input, 0, 1)
        
        # Weight slider
        add_layout.addWidget(QLabel("Weight:"), 1, 0)
        weight_layout = QHBoxLayout()
        
        self.weight_slider = QSlider(Qt.Horizontal)
        self.weight_slider.setMinimum(10)
        self.weight_slider.setMaximum(30)
        self.weight_slider.setValue(20)
        self.weight_slider.setTickPosition(QSlider.TicksBelow)
        self.weight_slider.setTickInterval(5)
        
        self.weight_label = QLabel("20")
        self.weight_slider.valueChanged.connect(
            lambda value: self.weight_label.setText(str(value))
        )
        
        weight_layout.addWidget(self.weight_slider)
        weight_layout.addWidget(self.weight_label)
        
        add_layout.addLayout(weight_layout, 1, 1)
        
        main_layout.addLayout(add_layout)
        
        # Button layout
        button_layout = QHBoxLayout()
        
        # Add button
        self.add_button = QPushButton("Add Pattern")
        self.add_button.clicked.connect(self.add_pattern)
        button_layout.addWidget(self.add_button)
        
        # Remove button
        self.remove_button = QPushButton("Remove Selected")
        self.remove_button.clicked.connect(self.remove_pattern)
        button_layout.addWidget(self.remove_button)
        
        button_layout.addStretch()
        
        # Save button
        self.save_button = QPushButton("Save")
        self.save_button.clicked.connect(self.save_preferences)
        button_layout.addWidget(self.save_button)
        
        # Cancel button
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)
        
        main_layout.addLayout(button_layout)
        
        # Set layout
        self.setLayout(main_layout)
    
    def load_patterns(self):
        """Load patterns from the manager into the list widget."""
        self.patterns_list.clear()
        
        for pref in self.pref_manager.get_patterns():
            item = QListWidgetItem()
            widget = PatternItemWidget(pref.pattern, pref.weight)
            
            # Set size for the item
            item.setSizeHint(widget.sizeHint())
            
            # Add to list
            self.patterns_list.addItem(item)
            self.patterns_list.setItemWidget(item, widget)
    
    def add_pattern(self):
        """Add a new pattern preference."""
        pattern = self.pattern_input.text().strip()
        
        if not pattern:
            QMessageBox.warning(self, "Input Error", "Please enter a pattern.")
            return
        
        weight = self.weight_slider.value()
        
        # Add to manager
        self.pref_manager.add_pattern(pattern, weight)
        
        # Clear input
        self.pattern_input.setText("")
        
        # Reload the list
        self.load_patterns()
    
    def remove_pattern(self):
        """Remove the selected pattern preference."""
        current_item = self.patterns_list.currentItem()
        
        if not current_item:
            QMessageBox.warning(self, "Selection Error", "Please select a pattern to remove.")
            return
        
        widget = self.patterns_list.itemWidget(current_item)
        pattern = widget.pattern_label.text()
        
        # Remove from manager
        self.pref_manager.remove_pattern(pattern)
        
        # Reload the list
        self.load_patterns()
    
    def save_preferences(self):
        """Save preferences and close dialog."""
        success = self.pref_manager.save_preferences()
        
        if success:
            self.preferences_updated.emit()
            self.accept()
        else:
            QMessageBox.warning(
                self, "Save Error", 
                "Error saving preferences. Please try again."
            )
    
    def get_preferences_manager(self) -> PreferencesManager:
        """Get the preferences manager."""
        return self.pref_manager