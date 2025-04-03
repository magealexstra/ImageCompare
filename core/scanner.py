"""
Scanner module for finding image files in specified directories.
"""
import os
from pathlib import Path
from typing import List, Set
import concurrent.futures
import multiprocessing

# Import resource manager
from core.resource_manager import get_resource_manager
from concurrent.futures import ThreadPoolExecutor

# Common image file extensions to scan for
IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp'}

def scan_single_directory(directory: str) -> List[str]:
    """
    Scan a single directory recursively for image files.
    
    Args:
        directory: Directory path to scan
        
    Returns:
        List of absolute paths to image files found
    
    Raises:
        ValueError: If the directory path is invalid
    """
    image_files = []
    dir_path = Path(directory)
    
    if not dir_path.exists() or not dir_path.is_dir():
        raise ValueError(f"Invalid directory path: {directory}")
    
    # Walk through directory tree
    for root, _, files in os.walk(dir_path):
        for file in files:
            file_path = os.path.join(root, file)
            ext = os.path.splitext(file_path)[1].lower()
            
            # Only add files with image extensions
            if ext in IMAGE_EXTENSIONS:
                image_files.append(file_path)
    
    return image_files

def find_image_files(directory_paths: List[str]) -> List[str]:
    """
    Recursively find all image files in the given directories using parallel processing.
    
    Args:
        directory_paths: List of directory paths to scan
        
    Returns:
        List of absolute paths to image files found
        
    Raises:
        ValueError: If any directory path is invalid
    """
    # Validate directories first to fail early if any are invalid
    for directory in directory_paths:
        dir_path = Path(directory)
        if not dir_path.exists() or not dir_path.is_dir():
            raise ValueError(f"Invalid directory path: {directory}")
    
    # Get resource recommendations from the resource manager
    resource_manager = get_resource_manager()
    resources = resource_manager.get_optimal_resources("scanning")
    
    # Use recommended thread count, but adjust based on directory count
    max_workers = min(resources["thread_count"], len(directory_paths) * 4)
    
    all_image_files = []
    
    # Use ThreadPoolExecutor for parallel directory scanning
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all directories to the thread pool
        future_to_dir = {executor.submit(scan_single_directory, dir_path): dir_path
                        for dir_path in directory_paths}
        
        # Collect results as they complete
        for future in concurrent.futures.as_completed(future_to_dir):
            dir_path = future_to_dir[future]
            try:
                image_files = future.result()
                all_image_files.extend(image_files)
            except Exception as e:
                # Log the error but continue processing other directories
                print(f"Error scanning directory {dir_path}: {e}")
    
    return all_image_files