"""
Memory optimization utilities for the bot
This module provides utilities to monitor and optimize memory usage
"""
import gc
import os
import psutil
from .config import logger


def get_memory_usage():
    """Get current memory usage in MB"""
    try:
        process = psutil.Process(os.getpid())
        mem_info = process.memory_info()
        return mem_info.rss / 1024 / 1024  # Convert to MB
    except Exception:
        return 0


def cleanup_memory(force=False):
    """
    Perform garbage collection and memory cleanup
    Args:
        force: If True, perform aggressive cleanup
    """
    try:
        before = get_memory_usage()
        
        if force:
            # Aggressive cleanup
            gc.collect(2)  # Full collection
        else:
            gc.collect()
        
        after = get_memory_usage()
        freed = before - after
        
        if freed > 0:
            logger.info(f"Memory cleanup: freed {freed:.2f} MB (before: {before:.2f} MB, after: {after:.2f} MB)")
        
        return freed
    except Exception as e:
        logger.error(f"Memory cleanup error: {e}")
        return 0


def log_memory_stats():
    """Log current memory statistics"""
    try:
        process = psutil.Process(os.getpid())
        mem_info = process.memory_info()
        mem_percent = process.memory_percent()
        
        logger.info(
            f"Memory Stats - RSS: {mem_info.rss / 1024 / 1024:.2f} MB, "
            f"VMS: {mem_info.vms / 1024 / 1024:.2f} MB, "
            f"Percent: {mem_percent:.2f}%"
        )
    except Exception as e:
        logger.error(f"Failed to log memory stats: {e}")


def check_memory_threshold(threshold_mb=500):
    """
    Check if memory usage exceeds threshold and cleanup if needed
    Args:
        threshold_mb: Memory threshold in MB
    Returns:
        True if cleanup was performed
    """
    try:
        current = get_memory_usage()
        if current > threshold_mb:
            logger.warning(f"Memory usage ({current:.2f} MB) exceeds threshold ({threshold_mb} MB)")
            cleanup_memory(force=True)
            return True
        return False
    except Exception as e:
        logger.error(f"Memory threshold check error: {e}")
        return False
