"""
Download Queue Manager - Manages sequential downloads with queue
"""
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class DownloadQueueStatus(Enum):
    """Download queue status"""
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"


@dataclass
class QueuedDownload:
    """Represents a download in the queue"""
    download_id: str
    url: str
    folder: str
    filename: str
    category: str
    comments: str
    connections: int = 4
    timeout: int = 30
    retry_count: int = 3
    speed_limit: int = 0  # KB/s, 0 = unlimited
    resume: bool = True
    skip_existing: bool = False
    use_proxy: bool = False
    proxy_url: str = ""
    start_immediately: bool = True
    auto_start: bool = True
    high_priority: bool = False
    post_action: str = "No Action"
    temp_folder: str = ""  # Temporary folder for storing .part files
    
    # Runtime state
    status: str = "queued"  # queued, running, paused, completed, failed, cancelled
    progress: int = 0
    size: int = 0
    speed: float = 0.0
    eta: str = "-"
    error_message: str = ""
    completed_path: str = ""
    added_at: str = field(default_factory=str)
    started_at: str = field(default_factory=str)
    completed_at: str = field(default_factory=str)


class DownloadQueueManager:
    """Manages sequential downloads"""
    
    def __init__(self, max_concurrent: int = 1):
        """
        Initialize queue manager
        
        Args:
            max_concurrent: Maximum concurrent downloads (default 1 for sequential)
        """
        self.max_concurrent = max_concurrent
        self.queue: List[QueuedDownload] = []
        self.active: Dict[str, QueuedDownload] = {}
        self.completed: Dict[str, QueuedDownload] = {}
        self.failed: Dict[str, QueuedDownload] = {}
        self.status = DownloadQueueStatus.IDLE
        self._paused = False
        
        # Callbacks
        self.on_started: Optional[Callable[[str], None]] = None
        self.on_progress: Optional[Callable[[str, int, float, str], None]] = None
        self.on_completed: Optional[Callable[[str, str], None]] = None
        self.on_failed: Optional[Callable[[str, str], None]] = None
        self.on_queue_changed: Optional[Callable[[], None]] = None
    
    def add_download(self, download: QueuedDownload) -> str:
        """
        Add download to queue
        
        Returns:
            Download ID
        """
        download.status = "queued"
        if download.high_priority:
            # Add to front of queue
            self.queue.insert(0, download)
        else:
            self.queue.append(download)

        if self.on_queue_changed:
            self.on_queue_changed()

        return download.download_id
    
    def get_next_download(self) -> Optional[QueuedDownload]:
        """Get next download to process"""
        if len(self.active) >= self.max_concurrent or not self.queue:
            return None
        
        if self._paused:
            return None
        
        download = self.queue.pop(0)
        self.active[download.download_id] = download
        download.status = "running"
        
        if self.on_queue_changed:
            self.on_queue_changed()
        
        if self.on_started:
            self.on_started(download.download_id)
        
        return download
    
    def update_progress(self, download_id: str, progress: int, speed: float = 0.0, eta: str = "-"):
        """Update download progress"""
        if download_id in self.active:
            self.active[download_id].progress = progress
            self.active[download_id].speed = speed
            self.active[download_id].eta = eta
            
            if self.on_progress:
                self.on_progress(download_id, progress, speed, eta)
    
    def mark_completed(self, download_id: str, completed_path: str = ""):
        """Mark download as completed"""
        if download_id in self.active:
            download = self.active.pop(download_id)
            download.status = "completed"
            download.progress = 100
            download.completed_path = completed_path
            self.completed[download_id] = download
            
            if self.on_completed:
                self.on_completed(download_id, completed_path)
            
            if self.on_queue_changed:
                self.on_queue_changed()
    
    def mark_failed(self, download_id: str, error_message: str = "Unknown error"):
        """Mark download as failed"""
        if download_id in self.active:
            download = self.active.pop(download_id)
            download.status = "failed"
            download.error_message = error_message
            self.failed[download_id] = download
            
            if self.on_failed:
                self.on_failed(download_id, error_message)
            
            if self.on_queue_changed:
                self.on_queue_changed()
    
    def cancel_download(self, download_id: str):
        """Cancel a download"""
        # If in active, mark as cancelled
        if download_id in self.active:
            download = self.active.pop(download_id)
            download.status = "cancelled"
            self.failed[download_id] = download
        # If in queue, remove it
        elif download_id in [d.download_id for d in self.queue]:
            self.queue = [d for d in self.queue if d.download_id != download_id]
        
        if self.on_queue_changed:
            self.on_queue_changed()
    
    def pause(self):
        """Pause queue processing"""
        self._paused = True
        self.status = DownloadQueueStatus.PAUSED
        if self.on_queue_changed:
            self.on_queue_changed()
    
    def resume(self):
        """Resume queue processing"""
        self._paused = False
        self.status = DownloadQueueStatus.RUNNING
        if self.on_queue_changed:
            self.on_queue_changed()
    
    def get_queue_length(self) -> int:
        """Get number of downloads in queue"""
        return len(self.queue)
    
    def get_active_count(self) -> int:
        """Get number of active downloads"""
        return len(self.active)
    
    def get_completed_count(self) -> int:
        """Get number of completed downloads"""
        return len(self.completed)
    
    def get_failed_count(self) -> int:
        """Get number of failed downloads"""
        return len(self.failed)
    
    def get_queue(self) -> List[QueuedDownload]:
        """Get all queued downloads"""
        return self.queue.copy()
    
    def get_active(self) -> List[QueuedDownload]:
        """Get all active downloads"""
        return list(self.active.values())
    
    def get_download(self, download_id: str) -> Optional[QueuedDownload]:
        """Get download by ID from any category"""
        if download_id in self.active:
            return self.active[download_id]
        if download_id in self.completed:
            return self.completed[download_id]
        if download_id in self.failed:
            return self.failed[download_id]
        # Check queue
        for d in self.queue:
            if d.download_id == download_id:
                return d
        return None
    
    def get_all_downloads(self) -> Dict[str, QueuedDownload]:
        """Get all downloads from all categories"""
        all_downloads = {}
        all_downloads.update(self.active)
        all_downloads.update(self.completed)
        all_downloads.update(self.failed)
        for d in self.queue:
            all_downloads[d.download_id] = d
        return all_downloads
    
    def clear_completed(self):
        """Clear all completed downloads"""
        self.completed.clear()
        if self.on_queue_changed:
            self.on_queue_changed()
    
    def clear_failed(self):
        """Clear all failed downloads"""
        self.failed.clear()
        if self.on_queue_changed:
            self.on_queue_changed()
    
    def get_statistics(self) -> dict:
        """Get queue statistics"""
        total_speed = sum(d.speed for d in self.active.values())
        return {
            "queued": len(self.queue),
            "active": len(self.active),
            "completed": len(self.completed),
            "failed": len(self.failed),
            "total_speed": total_speed,
            "status": self.status.value,
        }
