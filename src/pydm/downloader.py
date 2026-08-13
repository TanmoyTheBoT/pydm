from pathlib import Path
from urllib.parse import urlparse
import multiprocessing
import re

import httpx
from PySide6.QtCore import QThread, Signal
import time
import threading


def resolve_url_metadata(url: str, *, transport=None, timeout: float = 10.0):
    """Return the final redirected URL and a file name derived from the server headers."""
    raw_url = str(url).strip().replace("\r", "").replace("\n", "")
    if not raw_url:
        return "", "download.bin"

    client = httpx.Client(follow_redirects=True, timeout=timeout, transport=transport)
    try:
        with client.stream("GET", raw_url, follow_redirects=True, timeout=timeout) as response:
            response.raise_for_status()
            final_url = str(response.url)
            filename = get_filename(response, raw_url) or Path(urlparse(raw_url).path).name or "download.bin"
            return final_url, filename
    except Exception:
        final_url = raw_url
        filename = Path(urlparse(raw_url).path).name or "download.bin"
        return final_url, filename
    finally:
        try:
            client.close()
        except Exception:
            pass


def get_filename(response: httpx.Response, original_url: str) -> str:
    """
    Get filename from download response.

    Priority:
    1. Content-Disposition
    2. Redirected URL
    3. Original URL
    4. download.bin
    """

    content_disposition = response.headers.get("Content-Disposition")

    if content_disposition:
        match = re.search(
            r'filename\*?=(?:UTF-8\'\')?"?([^";]+)"?',
            content_disposition
        )

        if match:
            return Path(match.group(1)).name


    # Final redirected URL
    final_name = Path(
        urlparse(str(response.url)).path
    ).name

    if final_name:
        return final_name


    # Original URL
    original_name = Path(
        urlparse(original_url).path
    ).name

    if original_name:
        return original_name


    return "download.bin"


def unique_filepath(folder: Path, filename: str) -> Path:
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / filename
    if not path.exists():
        return path

    suffix = path.suffix
    stem = path.name[: -len(suffix)] if suffix else path.name

    counter = 2
    while True:
        candidate = folder / f"{stem}_{counter}{suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def download_file(url: str, output_dir: str = None):
    """
    Download file.

    Returns:
        saved file path
    """

    if output_dir is None:
        output_dir = str(Path.home() / "Downloads")

    output_path = Path(output_dir)
    output_path.mkdir(
        parents=True,
        exist_ok=True
    )


    with httpx.stream(
        "GET",
        url,
        follow_redirects=True,
        timeout=None,
    ) as response:


        response.raise_for_status()


        filename = get_filename(
            response,
            url
        )


        save_path = unique_filepath(output_path, filename)


        total_size = int(
            response.headers.get(
                "Content-Length",
                0
            )
        )


        downloaded = 0


        with open(
            save_path,
            "wb"
        ) as file:


            for chunk in response.iter_bytes(
                chunk_size=1024 * 64
            ):

                if chunk:

                    file.write(chunk)

                    downloaded += len(chunk)


                    yield {
                        "downloaded": downloaded,
                        "total": total_size,
                        "filename": filename,
                        "path": str(save_path),
                    }


    yield {
        "completed": True,
        "filename": filename,
        "path": str(save_path),
    }


class DownloadWorker(QThread):
    progress = Signal(int)
    message = Signal(str)
    finished = Signal(str)
    transfer_rate = Signal(float)
    eta_text = Signal(str)
    resume_capability = Signal(bool)
    filesize = Signal(float)

    def __init__(self, url, folder):
        super().__init__()
        self.url = str(url).strip().replace("\r", "").replace("\n", "")
        self.folder = folder
        self._pause_event = threading.Event()
        self._pause_event.clear()
        self._cancel = False

    def _probe_resume(self):
        try:
            client = httpx.Client()
            # Try HEAD first
            r = client.head(self.url, follow_redirects=True, timeout=0.5)
            if r.headers.get("Accept-Ranges", "").lower() == "bytes":
                return True
            # Fallback to small range request
            r2 = client.get(self.url, headers={"Range": "bytes=0-0"}, follow_redirects=True, timeout=0.5)
            return r2.status_code == 206
        except Exception:
            return False

    def run(self):
        try:
            client = httpx.Client()

            # determine resume capability (probe for server support)
            can_resume = self._probe_resume()
            # report resumable to UI
            self.resume_capability.emit(bool(can_resume))

            with client.stream("GET", self.url, follow_redirects=True, timeout=None) as response:
                response.raise_for_status()

                # filename
                cd = response.headers.get("Content-Disposition")
                filename = None
                if cd:
                    parts = [p.strip() for p in cd.split(";") if p.strip()]
                    for part in parts:
                        low = part.lower()
                        if low.startswith("filename*="):
                            val = part.split("=", 1)[1]
                            if "''" in val:
                                val = val.split("''", 1)[1]
                            filename = val.strip('"')
                            break
                        if low.startswith("filename="):
                            val = part.split("=", 1)[1]
                            filename = val.strip('"')
                            break

                if not filename:
                    filename = Path(urlparse(str(response.url)).path).name or Path(self.url).name or "download.bin"

                total_size = int(response.headers.get("Content-Length", 0))
                self.filesize.emit(total_size)

                save_path = Path(self.folder) / filename
                save_path.parent.mkdir(parents=True, exist_ok=True)

                downloaded = 0
                last_time = time.monotonic()
                last_downloaded = 0

                chunk_size = 1024 * 64
                with open(save_path, "wb") as fh:
                    for chunk in response.iter_bytes(chunk_size=chunk_size):
                        if self._cancel:
                            try:
                                fh.close()
                                save_path.unlink(missing_ok=True)
                            except Exception:
                                pass
                            self.message.emit("Cancelled")
                            return

                        while self._pause_event.is_set():
                            time.sleep(0.1)

                        if chunk:
                            fh.write(chunk)
                            downloaded += len(chunk)

                            now = time.monotonic()
                            elapsed = now - last_time
                            if elapsed >= 0.5:
                                delta = downloaded - last_downloaded
                                rate = delta / elapsed if elapsed > 0 else 0.0
                                self.transfer_rate.emit(rate)
                                if total_size and rate > 0:
                                    eta = int((total_size - downloaded) / rate)
                                    mins, secs = divmod(eta, 60)
                                    eta_text = f"{mins}m {secs}s"
                                else:
                                    eta_text = "-"
                                self.eta_text.emit(eta_text)
                                last_time = now
                                last_downloaded = downloaded

                            percent = int(downloaded / total_size * 100) if total_size else 0
                            self.progress.emit(percent)

                self.finished.emit(str(save_path))

        except Exception as e:
            self.message.emit(f"Error: {e}")

    def pause(self):
        self._pause_event.set()

    def resume(self):
        self._pause_event.clear()

    def cancel(self):
        self._cancel = True


class PartDownloader(QThread):
    # part_index, downloaded_bytes
    progress = Signal(int, int)
    finished = Signal(int, str)
    error = Signal(str)
    message = Signal(str)

    def __init__(self, url, start, end, part_index, folder, filename, existing=0):
        super().__init__()
        self.url = url
        self.range_start = start + existing
        self.range_end = end
        self.part_index = part_index
        self.folder = Path(folder)
        self.filename = filename
        self._pause_event = threading.Event()
        self._pause_event.clear()
        self._cancel = False
        self.existing = existing

    def run(self):
        try:
            client = httpx.Client()
            # If this part is already fully downloaded, emit finished immediately
            part_path = self.folder / f"{self.filename}.part{self.part_index}"
            total_part_size = self.range_end - (self.range_start - self.existing) + 1
            if part_path.exists() and part_path.stat().st_size >= total_part_size:
                self.finished.emit(self.part_index, str(part_path))
                return

            headers = {"Range": f"bytes={self.range_start}-{self.range_end}"}
            with client.stream("GET", self.url, headers=headers, follow_redirects=True, timeout=None) as r:
                r.raise_for_status()
                if r.status_code != 206:
                    self.error.emit(f"Server did not honor range request: {r.status_code}")
                    return
                self.message.emit(f"Part {self.part_index + 1} started")
                mode = "ab" if self.existing else "wb"
                downloaded = self.existing
                self.progress.emit(self.part_index, downloaded)
                chunk_size = 1024 * 64
                with open(part_path, mode) as fh:
                    for chunk in r.iter_bytes(chunk_size=chunk_size):
                        if self._cancel:
                            try:
                                fh.close()
                                if part_path.exists():
                                    part_path.unlink()
                            except Exception:
                                pass
                            self.error.emit("Cancelled")
                            return

                        while self._pause_event.is_set():
                            time.sleep(0.1)

                        if chunk:
                            fh.write(chunk)
                            downloaded += len(chunk)
                            self.progress.emit(self.part_index, downloaded)

                self.finished.emit(self.part_index, str(part_path))
        except Exception as e:
            self.error.emit(str(e))

    def pause(self):
        self._pause_event.set()

    def resume(self):
        self._pause_event.clear()

    def cancel(self):
        self._cancel = True


class SegmentedDownloadWorker(QThread):
    # overall percent
    progress = Signal(int)
    # part_index, percent
    part_progress = Signal(int, int)
    message = Signal(str)
    finished = Signal(str)
    transfer_rate = Signal(float)
    eta_text = Signal(str)
    resume_capability = Signal(bool)
    filesize = Signal(float)
    connections_changed = Signal(int)
    filename_changed = Signal(str)

    def __init__(self, url, folder, connections=None, temp_folder=None):
        super().__init__()
        self.url = str(url).strip().replace("\r", "").replace("\n", "")
        self.folder = folder  # Final destination folder
        self.temp_folder = temp_folder or folder  # Temp folder for .part files (default to folder if not specified)
        self.connections = None if connections is None else max(1, int(connections))
        self.manual_connections = self.connections if connections is not None else None
        self._parts = []
        self._cancel = False
        self._user_cancel = False
        self._pause_event = threading.Event()
        self._pause_event.clear()

    def _select_connection_count(self, total_size):
        if total_size <= 0:
            return max(2, multiprocessing.cpu_count() * 2)

        cpu_multiplier = max(1, multiprocessing.cpu_count())
        return max(2, cpu_multiplier * 2)

    def _probe_range_support(self, client):
        head = None
        total_size = 0
        try:
            head = client.head(self.url, follow_redirects=True, timeout=0.35)
            if head.status_code < 400:
                total_size = int(head.headers.get("Content-Length", 0) or 0)
                accept_ranges = (head.headers.get("Accept-Ranges", "") or "").lower()
                if accept_ranges == "bytes":
                    return True, total_size, head
            if head is not None:
                head.close()
        except Exception:
            head = None

        try:
            response = client.get(
                self.url,
                headers={"Range": "bytes=0-0"},
                follow_redirects=True,
                timeout=0.35,
                stream=True,
            )
            status = response.status_code
            if status == 206:
                content_range = response.headers.get("Content-Range", "") or ""
                if "/" in content_range:
                    try:
                        total_size = int(content_range.split("/", 1)[1])
                    except Exception:
                        total_size = int(response.headers.get("Content-Length", 0) or 0)
                else:
                    total_size = int(response.headers.get("Content-Length", 0) or 0)
                return True, total_size, response

            if status in (200, 416):
                content_range = response.headers.get("Content-Range", "") or ""
                if "/" in content_range:
                    try:
                        total_size = int(content_range.split("/", 1)[1])
                    except Exception:
                        total_size = int(response.headers.get("Content-Length", 0) or 0)
                else:
                    total_size = int(response.headers.get("Content-Length", 0) or 0)
                return False, total_size, response

            total_size = int(response.headers.get("Content-Length", 0) or 0)
            return False, total_size, response
        except Exception:
            try:
                response = client.get(self.url, follow_redirects=True, timeout=0.35, stream=True)
                if response.status_code >= 400:
                    response.close()
                    return False, 0, head
                total_size = int(response.headers.get("Content-Length", 0) or 0)
                return False, total_size, response
            except Exception:
                return False, 0, head

    def _single_connection_download(self, total_size, filename, can_resume=True):
        try:
            self.message.emit("Starting single connection download...")
            with httpx.Client().stream("GET", self.url, follow_redirects=True, timeout=None) as response:
                response.raise_for_status()
                filename = get_filename(response, self.url)
                if not filename:
                    filename = Path(urlparse(str(response.url)).path).name or Path(urlparse(self.url).path).name or "download.bin"
                save_path = unique_filepath(self.folder, filename)
                filename = save_path.name
                self.filename_changed.emit(filename)
                self.message.emit("Download started")
                self.progress.emit(0)
                self.transfer_rate.emit(0.0)
                self.eta_text.emit("-")

                total_size = int(response.headers.get("Content-Length", total_size))
                unknown_size = total_size <= 0
                self.filesize.emit(float(total_size))
                
                # Verify resume capability from actual response headers (always check, ignore probe result)
                accept_ranges = (response.headers.get("Accept-Ranges", "") or "").lower()
                actual_can_resume = accept_ranges == "bytes"
                self.resume_capability.emit(bool(actual_can_resume))
                
                # Store resume metadata for validation (ETag, Last-Modified)
                etag = response.headers.get("ETag", "")
                last_modified = response.headers.get("Last-Modified", "")
                if unknown_size:
                    self.progress.emit(0)
                    self.eta_text.emit("-")

                save_path = unique_filepath(self.folder, filename)
                save_path.parent.mkdir(parents=True, exist_ok=True)

                downloaded = 0
                last_time = time.monotonic()
                last_downloaded = 0
                last_percent = 0
                chunk_size = 1024 * 64

                try:
                    with open(save_path, "wb") as fh:
                        for chunk in response.iter_bytes(chunk_size=chunk_size):
                            if self._cancel:
                                try:
                                    fh.close()
                                    save_path.unlink(missing_ok=True)
                                except Exception:
                                    pass
                                self.message.emit("Cancelled")
                                return

                            while self._pause_event.is_set():
                                time.sleep(0.1)

                            if chunk:
                                fh.write(chunk)
                                downloaded += len(chunk)

                                now = time.monotonic()
                                elapsed = now - last_time
                                if elapsed >= 0.5:
                                    delta = downloaded - last_downloaded
                                    rate = delta / elapsed if elapsed > 0 else 0.0
                                    self.transfer_rate.emit(rate)
                                    if total_size and rate > 0:
                                        eta = int((total_size - downloaded) / rate)
                                        mins, secs = divmod(eta, 60)
                                        self.eta_text.emit(f"{mins}m {secs}s")
                                    else:
                                        self.eta_text.emit("-")
                                    last_time = now
                                    last_downloaded = downloaded

                                if unknown_size:
                                    if downloaded % (1024 * 1024) < chunk_size:
                                        self.message.emit(f"{filename} ({downloaded // 1024} KB)")
                                else:
                                    percent = int(downloaded / total_size * 100)
                                    if percent != last_percent:
                                        self.progress.emit(percent)
                                        last_percent = percent
                except httpx.ReadError as e:
                    self.message.emit(f"Error: {e}")
                    return

                if total_size > 0:
                    self.progress.emit(100)
                else:
                    self.progress.emit(100)
                self.transfer_rate.emit(0.0)
                self.eta_text.emit("-")
                self.finished.emit(str(save_path))
        except Exception as e:
            error_msg = str(e).strip()
            self.message.emit(f"Error: {error_msg}")

    def run(self):
        try:
            self._cancel = False
            self._user_cancel = False
            self._pause_event.clear()
            self._parts = []
            self.connections = None
            self.progress.emit(0)
            self.transfer_rate.emit(0.0)
            self.eta_text.emit("-")
            client = httpx.Client()
            self.message.emit("Probing server for range support...")
            supports_range, total_size, probe_response = self._probe_range_support(client)
            self.resume_capability.emit(bool(supports_range))
            self.filesize.emit(float(total_size))

            filename = None
            if probe_response is not None:
                filename = get_filename(probe_response, self.url)
                try:
                    probe_response.close()
                except Exception:
                    pass
            if not filename:
                filename = Path(urlparse(self.url).path).name or "download.bin"
            save_path = unique_filepath(self.folder, filename)
            filename = save_path.name
            self.filename_changed.emit(filename)

            if not supports_range:
                self.connections = 1
                self.connections_changed.emit(self.connections)
                self.progress.emit(0)
                self.transfer_rate.emit(0.0)
                self.eta_text.emit("-")
                self.resume_capability.emit(False)
                self.message.emit("Server does not support ranged requests; using single connection")
                self._single_connection_download(total_size, filename, can_resume=False)
                return

            self.connections = self._select_connection_count(total_size)
            self.connections_changed.emit(self.connections)
            self.progress.emit(0)
            self.transfer_rate.emit(0.0)
            self.eta_text.emit("-")
            if self.connections == 1:
                self.message.emit("Using single connection")
            else:
                self.message.emit(f"Using {self.connections} connections")

            # compute ranges
            if total_size <= 0 or self.connections == 1:
                self.progress.emit(0)
                self.transfer_rate.emit(0.0)
                self.eta_text.emit("-")
                self.message.emit("Starting single-connection download...")
                # if we reached here, server supports ranges but we chose 1 connection
                self._single_connection_download(total_size, filename, can_resume=True)
                return

            self.progress.emit(0)
            self.transfer_rate.emit(0.0)
            self.eta_text.emit("-")
            self.message.emit("Starting multi-connection download...")
            part_size = total_size // self.connections
            ranges = []
            for i in range(self.connections):
                s = i * part_size
                e = (s + part_size - 1) if i < self.connections - 1 else total_size - 1
                ranges.append((s, e))

            # create parts
            total_downloaded = 0
            # part_totals will be populated with existing sizes when creating parts
            part_totals = {}
            part_paths = {}
            last_time = time.monotonic()
            last_downloaded = 0

            def on_part_progress(idx, downloaded_bytes):
                nonlocal total_downloaded, last_time, last_downloaded
                part_totals[idx] = downloaded_bytes
                total_downloaded = sum(part_totals.values())
                percent = int(total_downloaded / total_size * 100) if total_size else 0
                self.progress.emit(percent)
                part_pct = int(downloaded_bytes / (ranges[idx][1] - ranges[idx][0] + 1) * 100) if (ranges[idx][1] - ranges[idx][0] + 1) else 0
                self.part_progress.emit(idx, part_pct)
                self.message.emit(f"Part {idx + 1}/{self.connections}: {part_pct}%")

                now = time.monotonic()
                elapsed = now - last_time
                if elapsed >= 0.5:
                    delta = total_downloaded - last_downloaded
                    rate = delta / elapsed if elapsed > 0 else 0.0
                    self.transfer_rate.emit(rate)
                    if total_size and rate > 0:
                        eta = int((total_size - total_downloaded) / rate)
                        mins, secs = divmod(eta, 60)
                        self.eta_text.emit(f"{mins}m {secs}s")
                    else:
                        self.eta_text.emit("-")
                    last_time = now
                    last_downloaded = total_downloaded

            finished_count = 0
            error_occurred = False

            def _check_all_parts_done():
                if error_occurred:
                    all_stopped = all(not p.isRunning() for p in self._parts)
                    if all_stopped:
                        self.quit()
                elif finished_count == self.connections:
                    self.quit()

            def on_part_error(msg):
                nonlocal error_occurred
                if self._user_cancel:
                    return

                if not error_occurred:
                    error_occurred = True
                    self.message.emit(f"Part error: {msg}. Falling back to single-connection download.")
                    self._cancel = True
                    for p in self._parts:
                        try:
                            p.cancel()
                        except Exception:
                            pass
                _check_all_parts_done()

            def on_part_finished(idx, path):
                nonlocal finished_count
                if self._user_cancel and error_occurred:
                    _check_all_parts_done()
                    return

                finished_count += 1
                part_paths[idx] = path
                if finished_count == self.connections and not error_occurred:
                    # assemble
                    self.message.emit("Assembling downloaded parts...")
                    final_path = unique_filepath(self.folder, filename)
                    with open(final_path, "wb") as out:
                        for i in range(self.connections):
                            p = Path(part_paths[i])
                            with open(p, "rb") as pf:
                                out.write(pf.read())
                    # remove parts after successful assembly
                    for i in range(self.connections):
                        try:
                            p = Path(part_paths[i])
                            p.unlink(missing_ok=True)
                        except Exception:
                            pass
                    # emit final signals
                    self.progress.emit(100)
                    self.transfer_rate.emit(0.0)
                    self.eta_text.emit("-")
                    for i in range(self.connections):
                        try:
                            self.part_progress.emit(i, 100)
                        except Exception:
                            pass
                    self.finished.emit(str(final_path))
                    _check_all_parts_done()
                else:
                    _check_all_parts_done()

            # start part downloaders (detect existing part sizes to resume)
            for idx, (s, e) in enumerate(ranges):
                part_path = Path(self.temp_folder) / f"{filename}.part{idx}"
                existing = 0
                try:
                    if part_path.exists():
                        existing = part_path.stat().st_size
                except Exception:
                    existing = 0
                # record existing bytes for progress calculations
                part_totals[idx] = existing
                part = PartDownloader(self.url, s, e, idx, self.temp_folder, filename, existing=existing)
                part.progress.connect(on_part_progress)
                part.finished.connect(on_part_finished)
                part.error.connect(on_part_error)
                part.message.connect(self.message.emit)
                self._parts.append(part)
            # start parts
            for p in self._parts:
                p.start()

            self.message.emit("Download parts started")
            # run a local event loop so queued cross-thread part signals are processed
            self.exec()

            # wait for parts after event loop exits
            for p in self._parts:
                p.wait()

            if error_occurred and not self._user_cancel:
                self.message.emit("Retrying with single connection after segmented download failure...")
                # remove any temporary part files from this download attempt
                for idx in range(self.connections):
                    temp_path = Path(self.temp_folder) / f"{filename}.part{idx}"
                    try:
                        temp_path.unlink(missing_ok=True)
                    except Exception:
                        pass
                self._cancel = False
                self._pause_event.clear()
                self.progress.emit(0)
                self.transfer_rate.emit(0.0)
                self.eta_text.emit("-")
                self._single_connection_download(total_size, filename)
                return

        except Exception as e:
            error_msg = str(e).strip()
            self.message.emit(f"Error: {error_msg}")

    def pause(self):
        self._pause_event.set()
        self.message.emit("Paused")
        for p in self._parts:
            try:
                p.pause()
            except Exception:
                pass

    def resume(self):
        self._pause_event.clear()
        self.message.emit("Resuming...")
        for p in self._parts:
            try:
                p.resume()
            except Exception:
                pass

    def cancel(self):
        self._cancel = True
        self._user_cancel = True
        self._pause_event.clear()
        for p in self._parts:
            try:
                p.cancel()
            except Exception:
                pass