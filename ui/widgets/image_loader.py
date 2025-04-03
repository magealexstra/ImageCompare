"""
Image loader module for asynchronous image loading and caching.
"""
import os
from typing import Dict, Callable, Optional, List, Tuple
from pathlib import Path
import threading
import queue
import time
import gc

from PySide6.QtCore import QObject, Signal, QSize, Qt
from PIL import Image, ImageQt

from core.file_handler import MemoryMappedImage, batch_process_images
from PySide6.QtGui import QPixmap, QImage

# Import resource manager
from core.resource_manager import get_resource_manager

class ImageLoadRequest:
    """Class representing an image load request with priorities and callbacks."""
    
    def __init__(self, 
                 image_path: str, 
                 target_size: QSize,
                 callback: Callable[[str, QPixmap, bool], None],
                 priority: int = 0,
                 load_full_res: bool = True,
                 memory_efficient: bool = True):
        """
        Initialize a new image load request.
        
        Args:
            image_path: Path to the image file
            target_size: Target size for the scaled image
            callback: Callback function to call when image is loaded
            priority: Priority of the request (higher = more important)
            load_full_res: Whether to load full resolution after thumbnail
        """
        self.image_path = image_path
        self.target_size = target_size
        self.callback = callback
        self.priority = priority
        self.load_full_res = load_full_res
        self.memory_efficient = memory_efficient
        self.timestamp = time.time()
    
    def __lt__(self, other):
        """Compare requests by priority."""
        if self.priority == other.priority:
            # If priorities are equal, older requests come first
            return self.timestamp < other.timestamp
        return self.priority > other.priority

class ImageCache:
    """Thread-safe cache for loaded images."""
    
    def __init__(self, max_size: int = 50):
        """
        Initialize the image cache.
        
        Args:
            max_size: Maximum number of images to keep in cache
        """
        self.cache: Dict[str, Dict[QSize, QPixmap]] = {}
        self.max_size = max_size
        self.lock = threading.RLock()
        self.access_times: Dict[str, float] = {}
    
    def get(self, image_path: str, size: QSize, memory_efficient: bool = True) -> Optional[QPixmap]:
        """
        Get an image from the cache if available.
        
        Args:
            image_path: Path to the image
            size: Requested size
            
        Returns:
            Cached pixmap or None if not in cache
        """
        with self.lock:
            if image_path in self.cache:
                # Update access time
                self.access_times[image_path] = time.time()
                
                # Check if the exact size is in cache
                if size in self.cache[image_path]:
                    return self.cache[image_path][size]
                
                # For memory-efficient mode, we prefer the exact size or smaller sizes
                if memory_efficient:
                    # First try exact size
                    if size in self.cache[image_path]:
                        return self.cache[image_path][size]
                    
                    # Then try to find a size that's not too much larger to avoid scaling large images
                    best_size = None
                    best_area_ratio = float('inf')
                    
                    for cached_size in self.cache[image_path].keys():
                        # Skip sizes smaller than what we need
                        if cached_size.width() < size.width() or cached_size.height() < size.height():
                            continue
                            
                        # Calculate ratio of areas (1.0 would be perfect match)
                        target_area = size.width() * size.height()
                        cached_area = cached_size.width() * cached_size.height()
                        area_ratio = cached_area / target_area
                        
                        # If ratio is < 1.5 (not too much bigger), and better than previous best
                        if area_ratio < 1.5 and area_ratio < best_area_ratio:
                            best_size = cached_size
                            best_area_ratio = area_ratio
                    
                    if best_size:
                        # Scale down the better size
                        pixmap = self.cache[image_path][best_size]
                        scaled = pixmap.scaled(
                            size,
                            Qt.KeepAspectRatio,
                            Qt.SmoothTransformation
                        )
                        # Cache the scaled version
                        self.cache[image_path][size] = scaled
                        return scaled
                else:
                    # Traditional approach - check if we have a larger version that can be scaled down
                    for cached_size, pixmap in self.cache[image_path].items():
                        if cached_size.width() >= size.width() and cached_size.height() >= size.height():
                            # Scale down the larger version
                            scaled = pixmap.scaled(
                                size,
                                Qt.KeepAspectRatio,
                                Qt.SmoothTransformation
                            )
                            # Cache the scaled version
                            self.cache[image_path][size] = scaled
                            return scaled
            
            return None
    
    def put(self, image_path: str, size: QSize, pixmap: QPixmap):
        """
        Add an image to the cache.
        
        Args:
            image_path: Path to the image
            size: Size of the image
            pixmap: Pixmap to cache
        """
        with self.lock:
            # Check if we need to make room in the cache
            if len(self.cache) >= self.max_size:
                self._cleanup()
            
            # Add to cache
            if image_path not in self.cache:
                self.cache[image_path] = {}
                self.access_times[image_path] = time.time()
            
            self.cache[image_path][size] = pixmap
            self.access_times[image_path] = time.time()
    
    def _cleanup(self):
        """Remove least recently accessed images to make room."""
        if not self.access_times:
            return
            
        # Sort by access time (oldest first)
        sorted_paths = sorted(
            self.access_times.items(),
            key=lambda x: x[1]
        )
        
        # Remove oldest entries until we're under the limit
        for path, _ in sorted_paths:
            if len(self.cache) < self.max_size:
                break
                
            if path in self.cache:
                del self.cache[path]
                del self.access_times[path]

class ImageLoaderSignals(QObject):
    """Signals for the ImageLoader class."""
    image_loaded = Signal(str, QPixmap, bool)  # path, pixmap, is_thumbnail

class ImageLoader(QObject):
    """
    Thread-safe asynchronous image loader with prioritization and caching.
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Create signals object
        self.signals = ImageLoaderSignals()
        
        # Get resource manager recommendations
        self.resource_manager = get_resource_manager()
        resources = self.resource_manager.get_optimal_resources("image_loading")
        
        # Create image cache with adaptive size
        cache_size = max(50, min(200, resources["batch_size"]))
        self.cache = ImageCache(max_size=cache_size)
        
        # Create request queue with priority
        self.queue = queue.PriorityQueue()
        
        # Create worker threads based on recommendations
        self.worker_threads = []
        self.worker_count = max(2, min(4, resources["thread_count"] // 2))
        self.running = True
        
        # Start worker threads
        for _ in range(self.worker_count):
            thread = threading.Thread(target=self._worker, daemon=True)
            thread.start()
            self.worker_threads.append(thread)
        
        # Register for resource updates
        self.resource_manager.register_monitoring_callback(self._on_resource_update)
        
        # Track active requests to avoid duplicates
        self.active_requests = set()
        self.active_requests_lock = threading.Lock()
    
    def load_image(self, 
                  image_path: str, 
                  target_size: QSize,
                  callback: Callable[[str, QPixmap, bool], None],
                  priority: int = 0,
                  load_full_res: bool = True):
        """
        Queue an image to be loaded asynchronously.
        
        Args:
            image_path: Path to the image
            target_size: Target size for scaling
            callback: Function to call when image is loaded
            priority: Request priority (higher = more important)
            load_full_res: Whether to load full resolution after thumbnail
        """
        # Detect large files for memory-efficient loading
        is_large_file = False
        try:
            file_size = os.path.getsize(image_path)
            # Files over 4MB are considered large (can be customized)
            is_large_file = file_size > 4 * 1024 * 1024
        except:
            pass
            
        # Check if already in cache
        cached = self.cache.get(image_path, target_size, memory_efficient=is_large_file)
        if cached:
            # Call callback immediately with cached image
            callback(image_path, cached, False)
            return
            
        # Create request
        request = ImageLoadRequest(
            image_path=image_path,
            target_size=target_size,
            memory_efficient=is_large_file,
            callback=callback,
            priority=priority,
            load_full_res=load_full_res
        )
        
        # Add to queue
        with self.active_requests_lock:
            request_key = (image_path, target_size.width(), target_size.height())
            if request_key not in self.active_requests:
                self.active_requests.add(request_key)
                self.queue.put(request)
    
    def preload_images(self, image_paths: List[str], thumbnail_size: QSize):
        """
        Preload a set of images with low priority.
        
        Args:
            image_paths: List of image paths to preload
            thumbnail_size: Size for thumbnails
        """
        for path in image_paths:
            # Use a dummy callback since we're just preloading
            self.load_image(
                image_path=path,
                target_size=thumbnail_size,
                callback=lambda *args: None,
                priority=-10,  # Low priority
                load_full_res=False  # Just load thumbnails for preloading
            )
    
    def _worker(self):
        """Worker thread to process image loading requests."""
        while self.running:
            try:
                # Get next request from queue
                request = self.queue.get(timeout=0.5)
                
                # Process request
                self._process_request(request)
                
                # Mark task as done
                self.queue.task_done()
                
            except queue.Empty:
                # No requests, just continue
                continue
            except Exception as e:
                # Log error and continue
                print(f"Error in ImageLoader worker: {e}")
    
    def _process_request(self, request: ImageLoadRequest):
        """
        Process an image loading request.
        
        Args:
            request: The request to process
        """
        try:
            path = request.image_path
            
            # Remove from active requests when done
            request_key = (path, request.target_size.width(), request.target_size.height())
            
            # Check if file exists
            if not os.path.exists(path):
                print(f"Image file not found: {path}")
                with self.active_requests_lock:
                    if request_key in self.active_requests:
                        self.active_requests.remove(request_key)
                return
            
            # First check if it's already in cache
            cached = self.cache.get(path, request.target_size)
            if cached:
                # Call callback with cached image
                request.callback(path, cached, False)
                with self.active_requests_lock:
                    if request_key in self.active_requests:
                        self.active_requests.remove(request_key)
                return
            
            # Load thumbnail first
            thumbnail_size = request.target_size
            thumbnail = self._load_and_scale_memory_efficient(path, thumbnail_size) if request.memory_efficient else self._load_and_scale(path, thumbnail_size)
            
            if thumbnail:
                # Cache the thumbnail
                self.cache.put(path, thumbnail_size, thumbnail)
                
                # Call callback with thumbnail
                request.callback(path, thumbnail, True)
                
                # If full resolution is requested, load it next
                if request.load_full_res:
                    # Load full image in background (using memory efficient approach if needed)
                    if request.memory_efficient:
                        # For large files, we don't load full resolution at original size
                        # Instead, load at a reasonable maximum size that's still larger than thumbnail
                        max_full_res = QSize(1200, 1200)  # Reasonable max size for display
                        full_image = self._load_and_scale_memory_efficient(path, max_full_res)
                    else:
                        # For smaller files, we can load at original size
                        original_size = QSize(0, 0)  # Original size
                        full_image = self._load_and_scale(path, original_size)
                    
                    if full_image:
                        # Cache the full image
                        actual_size = QSize(full_image.width(), full_image.height())
                        self.cache.put(path, actual_size, full_image)
                        
                        # Create properly scaled version if needed
                        if actual_size.width() > request.target_size.width() or actual_size.height() > request.target_size.height():
                            scaled = full_image.scaled(
                                request.target_size,
                                Qt.KeepAspectRatio,
                                Qt.SmoothTransformation
                            )
                            # Cache the scaled version
                            self.cache.put(path, request.target_size, scaled)
                            # Call callback with properly scaled image
                            request.callback(path, scaled, False)
                        else:
                            # Full image is already small enough
                            request.callback(path, full_image, False)
                            
                        # Force garbage collection after loading large images
                        if request.memory_efficient:
                            gc.collect()
            
            # Remove from active requests
            with self.active_requests_lock:
                if request_key in self.active_requests:
                    self.active_requests.remove(request_key)
                    
        except Exception as e:
            print(f"Error loading image {request.image_path}: {e}")
            # Remove from active requests on error
            with self.active_requests_lock:
                if request_key in self.active_requests:
                    self.active_requests.remove(request_key)
    
    def _load_and_scale(self, path: str, target_size: QSize) -> Optional[QPixmap]:
        """
        Load an image and scale it to the target size.
        
        Args:
            path: Path to the image
            target_size: Target size for scaling (0,0 for original size)
            
        Returns:
            Scaled pixmap or None if loading failed
        """
        try:
            # Load image
            pixmap = QPixmap(path)
            
            if pixmap.isNull():
                return None
                
            # If target size is not specified or is (0,0), return original
            if target_size.isEmpty() or (target_size.width() == 0 and target_size.height() == 0):
                return pixmap
                
            # Scale the image
            scaled = pixmap.scaled(
                target_size,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            
            return scaled
            
        except Exception as e:
            print(f"Error in _load_and_scale for {path}: {e}")
            return None
    
    def _load_and_scale_memory_efficient(self, path: str, target_size: QSize) -> Optional[QPixmap]:
        """
        Load an image and scale it to the target size using memory-mapped approach.
        Better for large images to minimize memory usage.
        
        Args:
            path: Path to the image
            target_size: Target size for scaling (0,0 for original size)
            
        Returns:
            Scaled pixmap or None if loading failed
        """
        try:
            # Create memory-mapped image
            with MemoryMappedImage(path) as img:
                # If target size is 0,0, use original size
                if target_size.isEmpty() or (target_size.width() == 0 and target_size.height() == 0):
                    pil_img = img.get_pil_image()
                else:
                    # Get a thumbnail of the right size
                    pil_img = img.get_thumbnail((target_size.width(), target_size.height()))
                
                # Convert PIL image to QPixmap
                qimage = ImageQt.ImageQt(pil_img)
                pixmap = QPixmap.fromImage(qimage)
                
                return pixmap
                
        except Exception as e:
            print(f"Error in _load_and_scale_memory_efficient for {path}: {e}")
            # Fall back to standard loading if memory mapping fails
            return self._load_and_scale(path, target_size)
    
    def _on_resource_update(self, cpu_percent, memory_percent):
        """Handle system resource updates."""
        # Adjust cache size based on memory pressure
        if memory_percent > 80:
            # Under high memory pressure, reduce cache size
            self.cache.max_size = 25
        elif memory_percent > 60:
            # Under moderate memory pressure
            self.cache.max_size = 50
        else:
            # Normal memory pressure
            resources = self.resource_manager.get_optimal_resources("image_loading")
            self.cache.max_size = max(50, min(200, resources["batch_size"]))
    
    def shutdown(self):
        """Shut down the worker threads."""
        self.running = False
        
        # Unregister from resource manager
        self.resource_manager.unregister_monitoring_callback(self._on_resource_update)
        
        # Wait for threads to finish
        for thread in self.worker_threads:
            if thread.is_alive():
                thread.join(timeout=0.5)