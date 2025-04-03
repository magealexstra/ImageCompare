"""
Resource manager module for adaptive system resource management.
"""
import os
import platform
import psutil
import threading
import time
from typing import Dict, Optional, Tuple, Callable

# Default resource settings if system detection fails
DEFAULT_CPU_COUNT = 16  # Balanced setting for AMD Ryzen 9 9900X (leaving cores for OS & other apps)
DEFAULT_MEMORY_LIMIT = 6 * 1024 * 1024 * 1024  # 6GB (modest for a 30GB system, leaving memory for other apps)
DEFAULT_THREAD_COUNT = 16  # ~70% of logical cores
DEFAULT_PROCESS_COUNT = 8  # ~70% of physical core count (12)
DEFAULT_BATCH_SIZE = 200  # Balanced for memory vs other applications

class ResourceManager:
    """
    Adaptive resource manager that detects system capabilities
    and provides optimal resource allocation strategies.
    """
    
    def __init__(self):
        # System capabilities
        self.cpu_count = self._detect_cpu_count()
        self.total_memory = self._detect_total_memory()
        self.platform_name = self._detect_platform()
        self.gpu_available = self._detect_gpu()
        
        # Current usage tracking
        self.current_cpu_usage = 0
        self.current_memory_usage = 0
        
        # Resource allocation settings
        self.recommended_thread_count = self._calculate_thread_count()
        self.recommended_process_count = self._calculate_process_count()
        self.recommended_batch_size = self._calculate_batch_size()
        self.memory_limit = self._calculate_memory_limit()
        
        # Monitoring
        self.monitoring_active = False
        self.monitoring_thread = None
        self.monitoring_interval = 1.0  # seconds
        self.monitoring_callbacks = []
        # Strategy
        self.strategy = "balanced"  # balanced, performance, memory
        
        # Apply system-specific optimizations
        self.optimize_for_current_system()
        self.strategy = "balanced"  # balanced, performance, memory
    
    def _detect_cpu_count(self) -> int:
        """Detect the number of CPU cores."""
        try:
            # Get logical CPU count
            cpu_count = os.cpu_count() or DEFAULT_CPU_COUNT
            
            # Use psutil for more accurate information
            if hasattr(psutil, 'cpu_count'):
                physical_count = psutil.cpu_count(logical=False) or cpu_count
                logical_count = psutil.cpu_count(logical=True) or cpu_count
                
                # If we have hyperthreading, we might want to use physical count
                # for some operations, but for now return logical count
                return logical_count
            
            return cpu_count
        except Exception as e:
            print(f"Error detecting CPU count: {e}")
            return DEFAULT_CPU_COUNT
    
    def _detect_total_memory(self) -> int:
        """Detect total system memory in bytes."""
        try:
            if hasattr(psutil, 'virtual_memory'):
                mem = psutil.virtual_memory()
                return mem.total
            return DEFAULT_MEMORY_LIMIT
        except Exception as e:
            print(f"Error detecting system memory: {e}")
            return DEFAULT_MEMORY_LIMIT
    
    def _detect_platform(self) -> str:
        """Detect the operating system platform."""
        try:
            return platform.system().lower()
        except Exception:
            return "unknown"
    
    def _detect_gpu(self) -> bool:
        """
        Detect if a GPU is available.
        Note: This is a simplified placeholder implementation.
        A real implementation would check for CUDA, OpenCL, etc.
        """
        try:
            # Placeholder for actual GPU detection
            # Would typically check for CUDA, OpenCL, etc.
            return False
        except Exception:
            return False
    
    def _calculate_thread_count(self) -> int:
        """Calculate the recommended number of threads for I/O operations."""
        # Balanced approach for AMD Ryzen 9 9900X, leaving resources for other applications
        logical_cores = self.cpu_count
        
        if self.platform_name == "windows":
            # Windows has higher thread creation overhead
            # Use approximately 1.5x logical cores, capped at 75% of total
            return min(int(logical_cores * 1.5), int(logical_cores * 0.75))
        else:
            # Linux/Unix can handle more threads efficiently
            # Use approximately 2x logical cores, capped at 75% of total for highest priority tasks
            return min(int(logical_cores * 2), int(logical_cores * 0.75))
    def _calculate_process_count(self) -> int:
        """Calculate the recommended number of processes for CPU-bound operations."""
        # For CPU-bound operations on AMD Ryzen 9 9900X, use a balanced approach
        # Use approximately 70% of physical cores to leave resources for other applications
        physical_cores = self.cpu_count // 2 if self.cpu_count > 1 else 1  # Estimate physical cores
        return max(1, int(physical_cores * 0.7))
    
    def _calculate_batch_size(self) -> int:
        """Calculate the recommended batch size based on system memory."""
        # Larger memory systems can handle larger batches
        memory_gb = self.total_memory / (1024**3)
        
        if memory_gb < 2:  # Less than 2GB
            return 25
        elif memory_gb < 4:  # 2-4GB
            return 50
        elif memory_gb < 8:  # 4-8GB
            return 100
        elif memory_gb < 16:  # 8-16GB
            return 150
        elif memory_gb < 32:  # 16-32GB (your system)
            return 200
        else:  # 32GB+
            return 300
    
    def _calculate_memory_limit(self) -> int:
        """Calculate memory usage limit in bytes."""
        # Use at most 40% of total memory to leave room for other applications
        # For a 30GB system, this would be around 12GB
        return int(self.total_memory * 0.4)
    
    def get_optimal_resources(self, operation_type: str = "default") -> Dict[str, int]:
        """
        Get optimal resource allocation based on operation type and system state.
        
        Args:
            operation_type: Type of operation (scanning, hashing, image_loading)
            
        Returns:
            Dictionary with recommended resource settings
        """
        # Start with base recommendations
        resources = {
            "thread_count": self.recommended_thread_count,
            "process_count": self.recommended_process_count,
            "batch_size": self.recommended_batch_size,
            "memory_limit": self.memory_limit
        }
        
        # Adjust based on operation type
        if operation_type == "scanning":
            # File scanning is I/O bound, so use more threads but be balanced
            # For a 24-thread system, use about 32 threads (still I/O bound, but not excessive)
            resources["thread_count"] = min(self.cpu_count * 1.5, 32)
            resources["process_count"] = 1  # Scanning doesn't benefit from multiple processes
            
        elif operation_type == "hashing":
            # Hashing is CPU bound, so use more processes
            resources["process_count"] = self.recommended_process_count
            resources["thread_count"] = 1  # Threads don't help with CPU-bound tasks
            
        elif operation_type == "image_loading":
            # Image loading is mixed I/O and CPU
            # Use a moderate number of threads for UI responsiveness
            resources["thread_count"] = min(int(self.cpu_count * 0.5), 12)
            resources["process_count"] = 1  # Loading in the main process for simplicity
        
        # Adjust based on current system load
        if self.current_cpu_usage > 80:
            # System is under heavy CPU load, reduce parallel operations
            resources["thread_count"] = max(2, resources["thread_count"] // 2)
            resources["process_count"] = max(1, resources["process_count"] // 2)
        
        if self.current_memory_usage > 70:
            # System is under heavy memory pressure, reduce batch size
            resources["batch_size"] = max(10, resources["batch_size"] // 2)
            resources["memory_limit"] = int(resources["memory_limit"] * 0.7)
        
        # Adjust based on strategy
        if self.strategy == "performance":
            # Prioritize performance over memory usage
            # But still keep it reasonable to not impact the system too much
            resources["thread_count"] = min(resources["thread_count"] * 1.5, 48)
            resources["process_count"] = min(resources["process_count"] + 2, int(self.cpu_count * 0.8))
            resources["batch_size"] = int(resources["batch_size"] * 1.2)
            
        elif self.strategy == "memory":
            # Prioritize memory efficiency over performance
            resources["thread_count"] = max(2, resources["thread_count"] // 2)
            resources["process_count"] = max(1, resources["process_count"] // 2)
            resources["batch_size"] = max(10, resources["batch_size"] // 2)
            resources["memory_limit"] = int(resources["memory_limit"] * 0.6)
        
        return resources
    
    def optimize_for_current_system(self):
        """
        Apply optimizations specific to the current system (AMD Ryzen 9 9900X with 30GB RAM).
        This method fine-tunes settings specifically for the detected hardware.
        """
        # Get current CPU model info
        cpu_model = self._get_cpu_model()
        memory_gb = self.total_memory / (1024**3)
        
        # Log system information
        print(f"Optimizing for detected system: {cpu_model}, {memory_gb:.1f}GB RAM")
        
        # AMD Ryzen 9 9900X specific optimizations
        if "AMD Ryzen 9" in cpu_model and self.cpu_count >= 20:
            print("Applying AMD Ryzen 9 9900X specific optimizations")
            
            # AMD Ryzen processors benefit from specific thread/core allocation strategies
            
            # For scanning (mostly I/O bound), use thread count optimized for AMD architecture
            # AMD CPUs have strong multithreading performance in I/O operations
            self.recommended_thread_count = min(int(self.cpu_count * 1.5), 32)
            
            # For CPU-bound operations, Ryzen processors benefit from process count
            # that aligns with CCX (Core Complex) boundaries - typically groups of 4 cores
            physical_cores = self.cpu_count // 2  # Estimate physical cores
            # Use 8 processes for 12-core Ryzen (leaving 4 cores free for system)
            self.recommended_process_count = max(1, int(physical_cores * 2/3))
            
            # Batch sizes can be moderately increased for high-memory AMD systems
            # AMD processors with high core counts benefit from larger batch processing
            if memory_gb >= 28:  # Detected ~30GB system
                self.recommended_batch_size = 180  # Balanced setting for 30GB system
                print(f"Using balanced batch size of {self.recommended_batch_size} for 30GB system")
            
            # Update memory limit based on physical RAM (40% of your 30GB, about 12GB)
            self.memory_limit = int(self.total_memory * 0.4)
            
            print(f"Optimized settings: threads={self.recommended_thread_count}, "
                  f"processes={self.recommended_process_count}, "
                  f"batch_size={self.recommended_batch_size}, "
                  f"memory_limit={self.memory_limit/(1024**3):.1f}GB")
    
    def _get_cpu_model(self) -> str:
        """Get CPU model name for system-specific optimizations."""
        try:
            if platform.system() == "Linux":
                with open("/proc/cpuinfo", "r") as f:
                    for line in f:
                        if "model name" in line:
                            return line.split(":")[1].strip()
            
            # If specific detection failed, use generic info
            return f"{platform.processor()} ({self.cpu_count} threads)"
        except Exception as e:
            print(f"Error detecting CPU model: {e}")
            return f"Unknown CPU ({self.cpu_count} threads)"
    
    def set_strategy(self, strategy: str):
        """
        Set the resource allocation strategy.
        
        Args:
            strategy: Strategy name (balanced, performance, memory)
        """
        if strategy in ("balanced", "performance", "memory"):
            self.strategy = strategy
        else:
            print(f"Unknown strategy: {strategy}, using 'balanced'")
            self.strategy = "balanced"
    
    def start_monitoring(self):
        """Start monitoring system resources."""
        if self.monitoring_active:
            return
            
        self.monitoring_active = True
        self.monitoring_thread = threading.Thread(
            target=self._monitoring_loop,
            daemon=True
        )
        self.monitoring_thread.start()
    
    def stop_monitoring(self):
        """Stop monitoring system resources."""
        self.monitoring_active = False
        if self.monitoring_thread and self.monitoring_thread.is_alive():
            self.monitoring_thread.join(timeout=2.0)
    
    def _monitoring_loop(self):
        """Background thread to monitor system resources."""
        while self.monitoring_active:
            try:
                # Update CPU usage
                self.current_cpu_usage = psutil.cpu_percent(interval=None)
                
                # Update memory usage
                mem = psutil.virtual_memory()
                self.current_memory_usage = mem.percent
                
                # Notify callbacks
                for callback in self.monitoring_callbacks:
                    try:
                        callback(self.current_cpu_usage, self.current_memory_usage)
                    except Exception as e:
                        print(f"Error in monitoring callback: {e}")
                
                # Sleep for the interval
                time.sleep(self.monitoring_interval)
                
            except Exception as e:
                print(f"Error in resource monitoring: {e}")
                time.sleep(self.monitoring_interval)
    
    def register_monitoring_callback(self, callback: Callable[[float, float], None]):
        """
        Register a callback to be notified of resource usage changes.
        
        Args:
            callback: Function to call with (cpu_percent, memory_percent)
        """
        if callback not in self.monitoring_callbacks:
            self.monitoring_callbacks.append(callback)
    
    def unregister_monitoring_callback(self, callback: Callable[[float, float], None]):
        """
        Unregister a previously registered callback.
        
        Args:
            callback: Function to unregister
        """
        if callback in self.monitoring_callbacks:
            self.monitoring_callbacks.remove(callback)
    
    def get_system_info(self) -> Dict[str, any]:
        """
        Get detailed system information.
        
        Returns:
            Dictionary with system information
        """
        info = {
            "platform": self.platform_name,
            "cpu_count": self.cpu_count,
            "total_memory_gb": round(self.total_memory / (1024**3), 2),
            "gpu_available": self.gpu_available,
            "current_cpu_usage": self.current_cpu_usage,
            "current_memory_usage": self.current_memory_usage,
            "recommended_thread_count": self.recommended_thread_count,
            "recommended_process_count": self.recommended_process_count,
            "recommended_batch_size": self.recommended_batch_size,
            "current_strategy": self.strategy
        }
        
        # Add detailed CPU info if available
        try:
            cpu_info = {}
            if hasattr(psutil, "cpu_freq"):
                freq = psutil.cpu_freq()
                if freq:
                    cpu_info["frequency_mhz"] = round(freq.current)
                    
            if platform.system() == "Linux":
                try:
                    with open("/proc/cpuinfo", "r") as f:
                        for line in f:
                            if "model name" in line:
                                cpu_info["model"] = line.split(":")[1].strip()
                                break
                except:
                    pass
                    
            info["cpu_info"] = cpu_info
        except:
            pass
            
        return info

# Singleton instance
_instance = None

def get_resource_manager(force_balanced: bool = False) -> ResourceManager:
    """
    Get the singleton instance of ResourceManager.
    
    Args:
        force_balanced: If True, force the resource manager to use balanced strategy
    
    Returns:
        ResourceManager instance
    """
    global _instance
    if _instance is None:
        _instance = ResourceManager()
        
    # Apply balanced mode if requested
    if force_balanced and _instance.strategy != "balanced":
        _instance.set_strategy("balanced")
        
    return _instance