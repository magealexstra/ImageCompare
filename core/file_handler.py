"""
File handler module for file operations like moving to trash and memory-efficient image loading.
"""
import os
import mmap
import io
import warnings
from pathlib import Path
from typing import List, Union, Optional, BinaryIO, Tuple

import numpy as np
from PIL import Image, ImageFile
import send2trash

# Enable loading of truncated images
ImageFile.LOAD_TRUNCATED_IMAGES = True

# Filter out common PIL EXIF warnings that don't affect functionality
warnings.filterwarnings("ignore", message="Corrupt EXIF data", category=UserWarning)

# Set a reasonable chunk size for processing (8 MB)
DEFAULT_CHUNK_SIZE = 8 * 1024 * 1024  # 8 MB

def move_to_trash(file_paths: List[Union[str, Path]]) -> List[str]:
    """
    Move files to the system trash.
    
    Args:
        file_paths: List of paths to files to be moved to trash
        
    Returns:
        List of paths that were successfully moved to trash
        
    Raises:
        FileNotFoundError: If a file does not exist
    """
    successfully_trashed = []
    
    for file_path in file_paths:
        path = Path(file_path)
        
        try:
            # Check if file exists
            if not path.exists():
                raise FileNotFoundError(f"File not found: {file_path}")
            
            # Move the file to trash
            send2trash.send2trash(str(path))
            
            # Add to list of successfully trashed files
            successfully_trashed.append(str(path))
            
        except Exception as e:
            # Log any errors but continue with other files
            print(f"Error moving {file_path} to trash: {str(e)}")
    
    return successfully_trashed

class MemoryMappedImage:
    """
    Memory-mapped image handler for efficient loading and processing of large images.
    """
    
    def __init__(self, file_path: Union[str, Path]):
        """
        Initialize with a file path.
        
        Args:
            file_path: Path to the image file
        """
        self.file_path = Path(file_path)
        self.file_obj = None
        self.mm = None
        self.pil_image = None
        self.size = None
        
    def __enter__(self):
        """Context manager entry."""
        try:
            self.open()
            return self
        except Exception as e:
            self.close()
            raise e
            
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
        
    def open(self):
        """Open the file and memory-map it."""
        if not self.file_path.exists():
            raise FileNotFoundError(f"Image file not found: {self.file_path}")
            
        # Open the file in binary mode
        self.file_obj = open(self.file_path, 'rb')
        
        try:
            # Create memory map (read-only)
            self.mm = mmap.mmap(self.file_obj.fileno(), 0, access=mmap.ACCESS_READ)
            
            # Create a PIL Image from the memory map
            self.pil_image = Image.open(io.BytesIO(self.mm))
            
            # Store the image size
            self.size = self.pil_image.size
            
            return self
        except Exception as e:
            self.close()
            raise e
    
    def close(self):
        """Close all open resources."""
        if self.pil_image:
            self.pil_image.close()
            self.pil_image = None
            
        if self.mm:
            self.mm.close()
            self.mm = None
            
        if self.file_obj:
            self.file_obj.close()
            self.file_obj = None
    
    def get_thumbnail(self, size: Tuple[int, int]) -> Image.Image:
        """
        Get a thumbnail of the image.
        
        Args:
            size: Desired thumbnail size (width, height)
            
        Returns:
            PIL Image thumbnail
        """
        if not self.pil_image:
            raise RuntimeError("Image not opened. Call open() first.")
            
        # Create a thumbnail (this loads only necessary data)
        thumbnail = self.pil_image.copy()
        thumbnail.thumbnail(size)
        return thumbnail
        
    def get_size(self) -> Tuple[int, int]:
        """
        Get the image dimensions.
        
        Returns:
            Tuple of (width, height)
        """
        if not self.pil_image:
            raise RuntimeError("Image not opened. Call open() first.")
            
        return self.size
        
    def get_pil_image(self) -> Image.Image:
        """
        Get the full PIL Image.
        Warning: This loads the entire image into memory.
        
        Returns:
            PIL Image
        """
        if not self.pil_image:
            raise RuntimeError("Image not opened. Call open() first.")
            
        return self.pil_image.copy()

def get_image_dimensions(file_path: Union[str, Path]) -> Tuple[int, int]:
    """
    Get image dimensions without loading the entire file.
    
    Args:
        file_path: Path to the image file
        
    Returns:
        Tuple of (width, height)
    """
    with MemoryMappedImage(file_path) as img:
        return img.get_size()

def load_image_thumbnail(file_path: Union[str, Path], size: Tuple[int, int]) -> Image.Image:
    """
    Load a thumbnail of an image efficiently.
    
    Args:
        file_path: Path to the image file
        size: Desired thumbnail size (width, height)
        
    Returns:
        PIL Image thumbnail
    """
    with MemoryMappedImage(file_path) as img:
        return img.get_thumbnail(size)

def batch_process_images(image_paths: List[str], batch_size: int = 50,
                        process_func=None, callback=None):
    """
    Process images in batches to limit memory usage.
    
    Args:
        image_paths: List of paths to images
        batch_size: Number of images per batch
        process_func: Function to process each image
        callback: Callback function(processed_count, total_count)
    """
    total_count = len(image_paths)
    processed_count = 0
    
    # Process in batches
    for i in range(0, total_count, batch_size):
        batch = image_paths[i:i+batch_size]
        
        # Process each image in the batch
        for path in batch:
            if process_func:
                process_func(path)
            
            processed_count += 1
            
            # Update progress
            if callback:
                callback(processed_count, total_count)