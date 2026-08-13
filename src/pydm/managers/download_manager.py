"""
PyDM Download Manager - Download tracking and management logic
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from enum import Enum
from datetime import datetime
from pathlib import Path


class DownloadStatus(Enum):
    """Download status enumeration"""
    IDLE = "Idle"
    PREPARING = "Preparing..."
    DOWNLOADING = "Downloading"
    PAUSED = "Paused"
    COMPLETED = "Completed"
    FAILED = "Failed"
    CANCELLED = "Cancelled"
    QUEUED = "Queued"


@dataclass
class DownloadInfo:
    """Download information container"""
    download_id: str
    url: str
    folder: str
    filename: str = ""
    size: int = 0
    downloaded: int = 0
    status: DownloadStatus = DownloadStatus.IDLE
    speed: float = 0.0
    eta_seconds: int = 0
    progress_percent: int = 0
    date_added: datetime = field(default_factory=datetime.now)
    date_completed: Optional[datetime] = None
    resume_capable: bool = False
    error_message: str = ""
    comments: str = ""
    connections: int = 1


class DownloadManager:
    """Manages download tracking and state"""
    
    def __init__(self):
        self.downloads: Dict[str, DownloadInfo] = {}
        self.id_counter = 0
    
    def create_download(self, url: str, folder: str, comments: str = "") -> str:
        """Create a new download entry"""
        self.id_counter += 1
        download_id = f"dl_{self.id_counter}"
        
        filename = Path(url.split('/')[-1]).name or "download.bin"
        
        self.downloads[download_id] = DownloadInfo(
            download_id=download_id,
            url=url,
            folder=folder,
            filename=filename,
            comments=comments,
        )
        
        return download_id
    
    def get_download(self, download_id: str) -> Optional[DownloadInfo]:
        """Get download info"""
        return self.downloads.get(download_id)
    
    def update_download(self, download_id: str, **kwargs):
        """Update download properties"""
        if download_id not in self.downloads:
            return
        
        download = self.downloads[download_id]
        for key, value in kwargs.items():
            if hasattr(download, key):
                setattr(download, key, value)
    
    def get_downloads_by_status(self, status: DownloadStatus) -> List[DownloadInfo]:
        """Get all downloads with specific status"""
        return [dl for dl in self.downloads.values() if dl.status == status]
    
    def get_all_downloads(self) -> List[DownloadInfo]:
        """Get all downloads"""
        return list(self.downloads.values())
    
    def remove_download(self, download_id: str) -> bool:
        """Remove download"""
        if download_id in self.downloads:
            del self.downloads[download_id]
            return True
        return False
    
    def clear_completed(self):
        """Remove all completed downloads"""
        to_remove = [
            dl.download_id for dl in self.downloads.values()
            if dl.status == DownloadStatus.COMPLETED
        ]
        for download_id in to_remove:
            self.remove_download(download_id)
    
    def get_total_speed(self) -> float:
        """Get total download speed"""
        return sum(
            dl.speed for dl in self.downloads.values()
            if dl.status == DownloadStatus.DOWNLOADING
        )
    
    def get_active_count(self) -> int:
        """Get number of active downloads"""
        return len(self.get_downloads_by_status(DownloadStatus.DOWNLOADING))
    
    def get_total_downloaded(self) -> int:
        """Get total bytes downloaded"""
        return sum(dl.downloaded for dl in self.downloads.values())
    
    def get_statistics(self) -> dict:
        """Get download statistics"""
        active = self.get_downloads_by_status(DownloadStatus.DOWNLOADING)
        completed = self.get_downloads_by_status(DownloadStatus.COMPLETED)
        paused = self.get_downloads_by_status(DownloadStatus.PAUSED)
        failed = self.get_downloads_by_status(DownloadStatus.FAILED)
        
        return {
            "total": len(self.downloads),
            "active": len(active),
            "completed": len(completed),
            "paused": len(paused),
            "failed": len(failed),
            "total_speed": self.get_total_speed(),
            "total_downloaded": self.get_total_downloaded(),
        }


class DownloadQueue:
    """Queue for managing download execution order"""
    
    def __init__(self, max_concurrent: int = 3):
        self.max_concurrent = max_concurrent
        self.queue: List[str] = []
        self.active: List[str] = []
    
    def enqueue(self, download_id: str):
        """Add download to queue"""
        if download_id not in self.queue and download_id not in self.active:
            self.queue.append(download_id)
    
    def dequeue(self) -> Optional[str]:
        """Get next download from queue"""
        if len(self.active) < self.max_concurrent and self.queue:
            download_id = self.queue.pop(0)
            self.active.append(download_id)
            return download_id
        return None
    
    def mark_completed(self, download_id: str):
        """Mark download as completed"""
        if download_id in self.active:
            self.active.remove(download_id)
    
    def get_queue_position(self, download_id: str) -> Optional[int]:
        """Get position in queue"""
        if download_id in self.queue:
            return self.queue.index(download_id) + 1
        return None
    
    def clear_queue(self):
        """Clear entire queue"""
        self.queue.clear()
        self.active.clear()
    
    def get_active_count(self) -> int:
        """Get number of active downloads"""
        return len(self.active)
