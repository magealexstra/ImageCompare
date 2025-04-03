"""
Duplicate finder module for identifying duplicate images based on perceptual hashes.
"""
from collections import defaultdict
from typing import Dict, List, Set, Callable, Optional

from core.hasher import group_by_hash

# Note: We now use the optimized parallel group_by_hash function from the hasher module

def identify_duplicates(hash_groups: Dict[str, List[str]], progress_callback: Optional[Callable] = None) -> Dict[str, List[str]]:
    """
    Filter hash groups to keep only those with more than one image (duplicates).
    
    Args:
        hash_groups: Dictionary mapping hash values to lists of image paths
        progress_callback: Optional callback function for progress tracking
        
    Returns:
        Dictionary containing only groups with more than one image
    """
    duplicate_groups = {}
    
    # For counting progress
    total = len(hash_groups)
    current = 0
    
    for hash_value, paths in hash_groups.items():
        # Only include groups with more than one image
        current += 1
        if len(paths) > 1:
            duplicate_groups[hash_value] = paths
            
        # Call progress callback if provided
        if progress_callback and callable(progress_callback):
            progress_callback(current, total)
    
    return duplicate_groups

def find_duplicates(image_paths: List[str], progress_callback: Optional[Callable] = None) -> Dict[str, List[str]]:
    """
    Find duplicate images in a single operation using parallel processing.
    
    Args:
        image_paths: List of paths to image files
        progress_callback: Optional callback function for progress tracking
        
    Returns:
        Dictionary containing only groups with more than one image (duplicates)
    """
    # Step 1: Group images by hash (using parallel processing)
    hash_groups = group_by_hash(image_paths, progress_callback)
    
    # Step 2: Filter to keep only duplicate groups
    # We don't pass the progress callback here since the heavy lifting is in hash calculation
    duplicate_groups = identify_duplicates(hash_groups)
    
    return duplicate_groups