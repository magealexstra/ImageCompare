"""
Hasher module for calculating perceptual hashes of images.
"""
from pathlib import Path
from typing import Optional, Union, List, Dict, Tuple
import os
import multiprocessing
from concurrent.futures import ProcessPoolExecutor
import concurrent.futures

# Import resource manager
from core.resource_manager import get_resource_manager

from PIL import Image, UnidentifiedImageError
import imagehash

def calculate_perceptual_hash(image_path: Union[str, Path]) -> Optional[str]:
    """
    Calculate a perceptual hash for an image using ImageHash library.
    
    Args:
        image_path: Path to the image file
        
    Returns:
        String representation of the perceptual hash,
        or None if the image could not be processed
        
    Raises:
        FileNotFoundError: If the image file does not exist
    """
    try:
        # Convert to Path object for consistent handling
        path = Path(image_path)
        
        # Check if file exists
        if not path.exists():
            raise FileNotFoundError(f"Image file not found: {image_path}")
        
        # Open the image and calculate its perceptual hash
        with Image.open(path) as img:
            # Convert to RGB if needed (for transparency handling)
            if img.mode != 'RGB':
                img = img.convert('RGB')
            
            # Calculate perceptual hash (using phash algorithm for best balance)
            hash_value = imagehash.phash(img)
            
            # Return the hash as a string for easy comparison
            return str(hash_value)
            
    except UnidentifiedImageError:
        # Handle case where file exists but is not a valid image
        print(f"Error: {image_path} is not a valid image file")
        return None
    except Exception as e:
        # Handle any other exceptions that might occur
        print(f"Error processing {image_path}: {str(e)}")
        return None

def batch_calculate_hashes(image_paths: List[str], callback=None) -> Dict[str, Optional[str]]:
    """
    Calculate perceptual hashes for multiple images in parallel using a process pool.
    
    Args:
        image_paths: List of paths to image files
        callback: Optional callback function(processed_count, total_count) for progress tracking
        
    Returns:
        Dictionary mapping image paths to their hash values (None for failed images)
    """
    results = {}
    
    # Get resource recommendations from the resource manager
    resource_manager = get_resource_manager()
    resources = resource_manager.get_optimal_resources("hashing")
    
    # Adjust batch size based on recommendations
    if len(image_paths) > resources["batch_size"]:
        # For very large collections, process in batches
        batch_size = resources["batch_size"]
        batches = [image_paths[i:i+batch_size] for i in range(0, len(image_paths), batch_size)]
        
        for batch in batches:
            # Process each batch
            batch_results = {}
            with ProcessPoolExecutor(max_workers=resources["process_count"]) as executor:
                future_to_path = {executor.submit(calculate_perceptual_hash, path): path for path in batch}
                
                # Process batch results
                for future in concurrent.futures.as_completed(future_to_path):
                    path = future_to_path[future]
                    try:
                        hash_value = future.result()
                        results[path] = hash_value
                    except Exception as e:
                        print(f"Error processing {path}: {e}")
                        results[path] = None
                        
                    # Call progress callback if provided
                    if callback and callable(callback):
                        callback(len(results), len(image_paths))
            
        return results
    else:
        # For smaller collections, process all at once
        with ProcessPoolExecutor(max_workers=resources["process_count"]) as executor:
            # Submit all images to the process pool
            future_to_path = {executor.submit(calculate_perceptual_hash, path): path
                             for path in image_paths}
            
            # Track progress
            total_count = len(image_paths)
            processed_count = 0
            
            # Collect results as they complete
            for future in concurrent.futures.as_completed(future_to_path):
                path = future_to_path[future]
                processed_count += 1
                
                try:
                    hash_value = future.result()
                    results[path] = hash_value
                except Exception as e:
                    # Handle exceptions in worker processes
                    print(f"Error processing {path}: {e}")
                    results[path] = None
                    
                # Call progress callback if provided
                if callback and callable(callback):
                    callback(processed_count, total_count)
    
    return results

def group_by_hash(image_paths: List[str], callback=None) -> Dict[str, List[str]]:
    """
    Group images by their perceptual hash values using parallel processing.
    
    Args:
        image_paths: List of paths to image files
        callback: Optional callback function for progress tracking
        
    Returns:
        Dictionary mapping hash values to lists of image paths with that hash
    """
    # Calculate hashes in parallel
    path_to_hash = batch_calculate_hashes(image_paths, callback)
    
    # Group images by hash
    hash_groups = {}
    
    for path, hash_value in path_to_hash.items():
        # Skip images that couldn't be hashed
        if hash_value is not None:
            if hash_value not in hash_groups:
                hash_groups[hash_value] = []
            hash_groups[hash_value].append(path)
    
    return hash_groups