#!/usr/bin/env python3
"""
Main entry point for the ImageCompare application.
"""
import sys
import os
from PySide6.QtWidgets import QApplication, QMessageBox
from ui.main_window import MainWindow
from core.resource_manager import get_resource_manager

def show_optimization_info():
    """Display information about system optimizations."""
    try:
        # Get optimized resource manager
        resource_manager = get_resource_manager()
        system_info = resource_manager.get_system_info()
        
        # Create info message
        info = (
            f"ImageCompare optimized for your system:\n"
            f"• CPU: {system_info.get('cpu_count', 'Unknown')} threads"
        )
        
        if 'cpu_info' in system_info and 'model' in system_info['cpu_info']:
            info += f" ({system_info['cpu_info']['model']})"
            
        info += (
            f"\n• Memory: {system_info.get('total_memory_gb', 'Unknown')} GB\n"
            f"• Using {system_info.get('recommended_process_count', 'Unknown')} processes for hashing\n"
            f"• Using up to {system_info.get('recommended_thread_count', 'Unknown')} threads for scanning\n"
            f"• Using batch size of {system_info.get('recommended_batch_size', 'Unknown')} for processing\n"
            f"\nOptimization strategy: {system_info.get('current_strategy', 'balanced').capitalize()}"
        )
        
        print(info.replace('•', '-'))
        return info
        
    except Exception as e:
        print(f"Error showing optimization info: {e}")
        return None

def main():
    """Main entry point for the application."""
    # Initialize resource manager with system optimizations
    get_resource_manager()
    # Create the Qt Application
    app = QApplication(sys.argv)
    
    # Set application information
    app.setApplicationName("ImageCompare")
    app.setOrganizationName("ImageCompare")
    app.setApplicationDisplayName("ImageCompare - Find and Delete Duplicate Images")
    
    # Create the main window
    window = MainWindow()
    
    # Show the window
    window.show()
    
    # Show optimization info (optional)
    if "--show-optimizations" in sys.argv or os.environ.get("IMAGECOMPARE_SHOW_OPTIMIZATIONS") == "1":
        optimization_info = show_optimization_info()
        if optimization_info:
            # Show the optimization info in a message box
            msg_box = QMessageBox()
            msg_box.setWindowTitle("System Optimizations")
            msg_box.setText(optimization_info)
            msg_box.setIcon(QMessageBox.Information)
            msg_box.exec()
    else:
        # Just print the info without showing dialog
        show_optimization_info()
    
    # Start the application event loop
    sys.exit(app.exec())

if __name__ == "__main__":
    main()