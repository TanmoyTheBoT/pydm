"""
PyDM Configuration and Data Storage Management
Handles paths, database, and persistent settings like IDM
"""
import os
import sqlite3
from pathlib import Path
from datetime import datetime
import getpass


class PyDMConfig:
    """Configuration and data management for PyDM"""
    
    def __init__(self):
        """Initialize PyDM config directory and database"""
        self.username = getpass.getuser()
        self.config_dir = self._get_config_dir()
        self.dwnl_data_dir = self.config_dir / "DwnlData" / self.username
        self.db_path = self.config_dir / "database.sqlite"
        self.unique_folder_counter = 0  # Counter for unique folder names (like IDM)
        
        # Create directories if they don't exist
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.dwnl_data_dir.mkdir(parents=True, exist_ok=True)
        
        # Load highest counter from existing folders
        self._load_existing_counter()
        
        # Initialize database
        self._init_database()
    
    def _load_existing_counter(self):
        """Load the highest counter from existing temp folders"""
        try:
            if self.dwnl_data_dir.exists():
                for folder in self.dwnl_data_dir.iterdir():
                    if folder.is_dir():
                        # Extract counter from folder name like "filename_1234"
                        folder_name = folder.name
                        parts = folder_name.rsplit("_", 1)
                        if len(parts) == 2:
                            try:
                                counter = int(parts[1])
                                self.unique_folder_counter = max(self.unique_folder_counter, counter)
                            except ValueError:
                                pass
        except Exception as e:
            print(f"[PyDMConfig] Error loading existing counter: {e}")
    
    def _get_config_dir(self) -> Path:
        r"""Get PyDM config directory: C:\Users\<username>\.config\pydm"""
        home = Path.home()
        config_dir = home / ".config" / "pydm"
        return config_dir
    
    def _init_database(self):
        """Initialize SQLite database for download history."""
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()

            if not self._table_exists(cursor, "downloads"):
                cursor.execute("""
                    CREATE TABLE downloads (
                        download_id TEXT PRIMARY KEY,
                        filename TEXT NOT NULL,
                        url TEXT NOT NULL,
                        save_folder TEXT NOT NULL,
                        category TEXT NOT NULL,
                        status TEXT DEFAULT 'pending',
                        total_size INTEGER DEFAULT 0,
                        downloaded_size INTEGER DEFAULT 0,
                        temp_folder TEXT,
                        comments TEXT,
                        connections INTEGER DEFAULT 4,
                        timeout INTEGER DEFAULT 30,
                        retry_count INTEGER DEFAULT 3,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        completed_at TIMESTAMP,
                        deleted_at TIMESTAMP
                    )
                """)

            # Create download parts table for segmented downloads
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS download_parts (
                    part_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    download_id TEXT NOT NULL,
                    part_number INTEGER NOT NULL,
                    start_byte INTEGER,
                    end_byte INTEGER,
                    downloaded_bytes INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'pending',
                    FOREIGN KEY (download_id) REFERENCES downloads(download_id)
                )
            """)
            
            # Create UI settings table for column widths, window geometry, etc.
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS ui_settings (
                    setting_key TEXT PRIMARY KEY,
                    setting_value TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"[PyDMConfig] Database initialization error: {e}")
    
    def get_download_temp_folder(self, download_id: str, filename: str) -> Path:
        """
        Get unique temp folder for download, like IDM:
        DwnlData/<username>/<filename>_<unique_counter>/
        Example: DwnlData/TanmoyTheBoT/PyDM-v0.0.1-Windows_1355/
        """
        # Increment counter and get next unique ID
        self.unique_folder_counter += 1
        unique_id = self.unique_folder_counter
        
        # Create folder name: filename_counter
        file_stem = Path(filename).stem  # Remove extension
        folder_name = f"{file_stem}_{unique_id}"
        
        temp_folder = self.dwnl_data_dir / folder_name
        temp_folder.mkdir(parents=True, exist_ok=True)
        return temp_folder
    
    def save_download(self, download_id: str, filename: str, url: str, 
                     save_folder: str, category: str, total_size: int = 0, 
                     temp_folder: str = None, **kwargs):
        """Save download metadata to database with only the fields this app actually uses."""
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()

            cursor.execute("""
                INSERT OR REPLACE INTO downloads 
                (download_id, filename, url, save_folder, category, status, total_size, temp_folder,
                 comments, connections, timeout, retry_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                download_id, filename, url, save_folder, category,
                kwargs.get('status', 'pending'),
                total_size, temp_folder,
                kwargs.get('comments', ''),
                kwargs.get('connections', 4),
                kwargs.get('timeout', 30),
                kwargs.get('retry_count', 3),
            ))

            conn.commit()
            conn.close()
        except Exception as e:
            print(f"[PyDMConfig] Error saving download: {e}")
    
    def _table_exists(self, cursor, table_name: str) -> bool:
        """Check whether a table exists."""
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
        return cursor.fetchone() is not None

    def update_download_status(self, download_id: str, status: str, 
                              downloaded_size: int = None, total_size: int = None):
        """Update download status and progress. Clean up temp folder if completed."""
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            if status == "completed":
                # Get temp folder before updating status
                cursor.execute("SELECT temp_folder FROM downloads WHERE download_id = ?", 
                             (download_id,))
                row = cursor.fetchone()
                temp_folder = row[0] if row else None
                
                # Update status with completion timestamp
                cursor.execute("""
                    UPDATE downloads 
                    SET status = ?, completed_at = CURRENT_TIMESTAMP
                    WHERE download_id = ?
                """, (status, download_id))
                
                conn.commit()
                conn.close()
                
                # Delete temp folder after successful completion
                if temp_folder:
                    temp_path = Path(temp_folder)
                    if temp_path.exists():
                        try:
                            import shutil
                            shutil.rmtree(temp_path, ignore_errors=True)
                            print(f"[PyDMConfig] Deleted temp folder: {temp_folder}")
                        except Exception as e:
                            print(f"[PyDMConfig] Error deleting temp folder {temp_folder}: {e}")
            else:
                update_query = "UPDATE downloads SET status = ?"
                params = [status]
                
                if downloaded_size is not None:
                    update_query += ", downloaded_size = ?"
                    params.append(downloaded_size)
                
                if total_size is not None:
                    update_query += ", total_size = ?"
                    params.append(total_size)
                
                update_query += " WHERE download_id = ?"
                params.append(download_id)
                
                cursor.execute(update_query, params)
                
                conn.commit()
                conn.close()
        except Exception as e:
            print(f"[PyDMConfig] Error updating download: {e}")
    
    def update_download_filename(self, download_id: str, filename: str):
        """Update the filename in database when actual filename is discovered (e.g., with _2 appended)"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE downloads 
                SET filename = ?
                WHERE download_id = ?
            """, (filename, download_id))
            
            conn.commit()
            conn.close()
            print(f"[PyDMConfig] [OK] Updated filename for {download_id}: {filename}")
        except Exception as e:
            print(f"[PyDMConfig] [ERROR] Error updating filename: {e}")
    
    def update_download_filepath(self, download_id: str, filepath: str):
        """Update the full filepath when download completes (stores actual saved path with unique name)"""
        try:
            from pathlib import Path
            filepath_obj = Path(filepath)
            filename = filepath_obj.name
            save_folder = str(filepath_obj.parent)
            
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            # Update both filename and save_folder to reflect actual saved location
            cursor.execute("""
                UPDATE downloads 
                SET filename = ?, save_folder = ?
                WHERE download_id = ?
            """, (filename, save_folder, download_id))
            
            conn.commit()
            conn.close()
            print(f"[PyDMConfig] [OK] Updated filepath for {download_id}:")
            print(f"[PyDMConfig]     - Filename: {filename}")
            print(f"[PyDMConfig]     - Folder: {save_folder}")
        except Exception as e:
            print(f"[PyDMConfig] [ERROR] Error updating filepath: {e}")
    
    def get_download(self, download_id: str):
        """Get a single download record"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT * FROM downloads 
                WHERE download_id = ? AND deleted_at IS NULL
            """, (download_id,))
            
            row = cursor.fetchone()
            conn.close()
            return dict(row) if row else None
        except Exception as e:
            print(f"[PyDMConfig] Error getting download: {e}")
            return None
    
    def get_all_downloads(self, include_deleted=False):
        """Get all downloads from database"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            if include_deleted:
                cursor.execute("SELECT * FROM downloads ORDER BY created_at DESC")
            else:
                cursor.execute("""
                    SELECT * FROM downloads 
                    WHERE deleted_at IS NULL 
                    ORDER BY created_at DESC
                """)
            
            downloads = [dict(row) for row in cursor.fetchall()]
            conn.close()
            return downloads
        except Exception as e:
            print(f"[PyDMConfig] Error reading downloads: {e}")
            return []
    
    def delete_download(self, download_id: str, delete_files=True):
        """Mark download as deleted and optionally remove temp files"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            # Mark as deleted in database
            cursor.execute("""
                UPDATE downloads 
                SET deleted_at = CURRENT_TIMESTAMP 
                WHERE download_id = ?
            """, (download_id,))
            
            conn.commit()
            
            # Get temp folder and delete if requested
            if delete_files:
                cursor.execute("SELECT temp_folder FROM downloads WHERE download_id = ?", 
                             (download_id,))
                row = cursor.fetchone()
                if row and row[0]:
                    temp_folder = Path(row[0])
                    if temp_folder.exists():
                        import shutil
                        shutil.rmtree(temp_folder, ignore_errors=True)
            
            conn.close()
        except Exception as e:
            print(f"[PyDMConfig] Error deleting download: {e}")
    
    def restore_download(self, download_id: str):
        """Restore a deleted download"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE downloads 
                SET deleted_at = NULL 
                WHERE download_id = ?
            """, (download_id,))
            
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"[PyDMConfig] Error restoring download: {e}")
    
    def cleanup_old_downloads(self, days=30):
        """Clean up downloads older than specified days"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            # Get old deleted downloads
            cursor.execute("""
                SELECT download_id, temp_folder FROM downloads 
                WHERE deleted_at IS NOT NULL 
                AND datetime(deleted_at) < datetime('now', '-' || ? || ' days')
            """, (days,))
            
            rows = cursor.fetchall()
            for download_id, temp_folder in rows:
                # Delete temp files
                if temp_folder:
                    temp_path = Path(temp_folder)
                    if temp_path.exists():
                        import shutil
                        shutil.rmtree(temp_path, ignore_errors=True)
                
                # Delete database record
                cursor.execute("DELETE FROM downloads WHERE download_id = ?", (download_id,))
            
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"[PyDMConfig] Error cleaning up downloads: {e}")
    
    def save_column_widths(self, column_widths: dict):
        """Save table column widths to database"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            # Save as JSON string
            import json
            widths_json = json.dumps(column_widths)
            
            cursor.execute("""
                INSERT OR REPLACE INTO ui_settings (setting_key, setting_value)
                VALUES ('column_widths', ?)
            """, (widths_json,))
            
            conn.commit()
            conn.close()
            print(f"[PyDMConfig] [OK] Column widths saved to database: {column_widths}")
        except Exception as e:
            print(f"[PyDMConfig] [ERROR] Error saving column widths: {e}")
    
    def load_column_widths(self) -> dict:
        """Load table column widths from database"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT setting_value FROM ui_settings 
                WHERE setting_key = 'column_widths'
            """)
            
            row = cursor.fetchone()
            conn.close()
            
            if row and row[0]:
                import json
                widths = json.loads(row[0])
                print(f"[PyDMConfig] [OK] Column widths loaded from database: {widths}")
                return widths
            print(f"[PyDMConfig] [INFO] No saved column widths found in database (first run)")
            return None
        except Exception as e:
            print(f"[PyDMConfig] [ERROR] Error loading column widths: {e}")
            return None


# Global config instance
_config_instance = None

def get_config() -> PyDMConfig:
    """Get or create global config instance"""
    global _config_instance
    if _config_instance is None:
        _config_instance = PyDMConfig()
    return _config_instance
