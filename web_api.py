import logging
import comtypes
from app.device.device_manager import get_device_manager

logger = logging.getLogger(__name__)

class WebApi:
    """The API exposed to JavaScript."""
    
    def __init__(self):
        self._dm = get_device_manager()
        self._active_scanner = None
        self._backup_cancelled = False
        self._backup_paused = False

    def get_devices(self):
        """Called by JS to refresh and get connected devices."""
        # Because pywebview calls this from a background thread, we must initialize COM for this thread.
        comtypes.CoInitialize()
        try:
            devices = self._dm.refresh()
            result = []
            for d in devices:
                result.append({
                    "pnp_id": d.pnp_id,
                    "name": d.display_name,
                    "manufacturer": d.manufacturer
                })
            return result
        except Exception as e:
            logger.error(f"Error getting devices for web: {e}", exc_info=True)
            return []
        finally:
            comtypes.CoUninitialize()

    def get_device_folders(self, pnp_id):
        """Returns top-level folder names on the device for the exclusion picker."""
        comtypes.CoInitialize()
        try:
            from app.device.mtp_manager import WPD_DEVICE_OBJECT_ID
            devices = self._dm.get_current_devices()
            phone = next((d for d in devices if d.pnp_id == pnp_id), None)
            if not phone:
                return []
            
            with self._dm.open_device(phone) as wpd:
                root_kids = wpd.list_children(WPD_DEVICE_OBJECT_ID)
                folders = []
                for kid in root_kids:
                    # These are storage objects (Internal storage, SD card etc.)
                    sub_kids = wpd.list_children(kid)
                    for sub in sub_kids:
                        obj = wpd.get_object_info(sub)
                        if obj and obj.name:
                            # Try to enumerate sub-children to confirm it's a folder
                            folders.append(obj.name)
                return sorted(set(folders))
        except Exception as e:
            logger.error(f"Error getting device folders: {e}", exc_info=True)
            return []
        finally:
            comtypes.CoUninitialize()

    def scan_device(self, pnp_id, excluded_folders=None):
        """Called by JS to scan the selected device."""
        comtypes.CoInitialize()
        try:
            from app.backup.scanner import Scanner
            
            # Find the specific device object
            devices = self._dm.get_current_devices()
            phone = next((d for d in devices if d.pnp_id == pnp_id), None)
            
            if not phone:
                return {"photos": 0, "videos": 0, "size_str": "0 B"}
            
            with self._dm.open_device(phone) as wpd:
                scanner = Scanner()
                self._active_scanner = scanner
                
                # Callback to send progress back to UI
                def cb(count, path):
                    import webview
                    import json
                    if webview.windows:
                        safe_path = json.dumps(path)
                        try:
                            webview.windows[0].evaluate_js(
                                f"if(window.updateScanProgress) updateScanProgress({count}, {safe_path});"
                            )
                        except Exception:
                            pass  # Window may have been disposed
                            
                res = scanner.scan(wpd, progress_cb=cb, extra_excluded=set(excluded_folders or []))
                self._last_scan_result = res
                
            def fmt_size(b):
                for unit in ("B", "KB", "MB", "GB", "TB"):
                    if b < 1024:
                        return f"{b:.1f} {unit}"
                    b /= 1024
                return f"{b:.1f} PB"

            return {
                "photos": res.photo_count,
                "videos": res.video_count,
                "size_str": fmt_size(res.total_size),
                "size_bytes": res.total_size
            }
        except Exception as e:
            logger.error(f"Error scanning for web: {e}", exc_info=True)
            return {"photos": 0, "videos": 0, "size_str": "Error", "size_bytes": 0}
        finally:
            self._active_scanner = None
            comtypes.CoUninitialize()

    def cancel_scan(self):
        """Cancels the currently active scan."""
        if self._active_scanner:
            self._active_scanner.cancel()
            return True
        return False

    def cancel_backup(self):
        self._backup_cancelled = True
        return True

    def pause_backup(self):
        self._backup_paused = True
        return True

    def resume_backup(self):
        self._backup_paused = False
        return True

    def open_url(self, url: str):
        import webbrowser
        webbrowser.open(url)
        return True

    def select_backup_folder(self, device_name: str):
        import webview
        import os
        import shutil
        
        if not webview.windows:
            return None
            
        result = webview.windows[0].create_file_dialog(webview.FOLDER_DIALOG)
        if result and len(result) > 0:
            base_dir = result[0]
            # Replace invalid characters in device name if any
            safe_name = "".join(c for c in device_name if c not in r'<>:"/\|?*')
            folder_name = f"BACKUP PBM - {safe_name}"
            
            # Prevent nesting if user selects the already created backup folder
            if os.path.basename(base_dir.rstrip(r"\/")) == folder_name:
                full_path = base_dir
            else:
                full_path = os.path.join(base_dir, folder_name)
            
            try:
                os.makedirs(full_path, exist_ok=True)
                usage = shutil.disk_usage(full_path)
                free_gb = usage.free / (1024**3)
                
                # Automatically save it to settings so dashboard can read it on next load
                from app.config.settings import Settings
                s = Settings()
                s.backup_folder = full_path
                s.save()
                
                return {"success": True, "path": full_path, "free_gb": f"{free_gb:.1f}", "free_bytes": usage.free}
            except Exception as e:
                logger.error(f"Error creating backup folder: {e}")
                return {"success": False, "error": str(e)}
        
        return {"success": False, "error": "No folder selected"}

    def get_free_space(self, path: str):
        """Returns the free space of a given path in GB."""
        import os
        import shutil
        try:
            if not path or not os.path.exists(path):
                return None
            usage = shutil.disk_usage(path)
            free_gb = usage.free / (1024**3)
            return {"free_gb_str": f"{free_gb:.1f} GB", "free_bytes": usage.free}
        except Exception as e:
            logger.error(f"Error getting free space for {path}: {e}")
            return None

    def start_backup(self, pnp_id, dest_dir):
        """Called by JS to start backing up the files from the last scan."""
        self._backup_cancelled = False
        self._backup_paused = False
        
        if not hasattr(self, "_last_scan_result") or not self._last_scan_result:
            return {"success": False, "error": "No scan results available. Please scan first."}
        
        comtypes.CoInitialize()
        try:
            from app.backup.transfer_manager import transfer_file
            
            devices = self._dm.get_current_devices()
            phone = next((d for d in devices if d.pnp_id == pnp_id), None)
            if not phone:
                return {"success": False, "error": "Device not found."}
                
            files = self._last_scan_result.all_files
            total_files = len(files)
            total_bytes = sum(f.size for f in files)
            
            if total_files == 0:
                return {"success": False, "error": "No files to backup."}
            
            from app.config.settings import Settings
            app_settings = Settings()
            verify_hash = app_settings.hash_verification
            
            copied_files = 0
            copied_bytes = 0
            
            import webview
            import json
            import os
            import time
            from collections import deque
            
            last_report_time = time.time()
            last_bytes_copied = 0
            speed_history = deque(maxlen=10)  # Keep last 10 samples (~2 seconds)
            
            def report_progress(current_pct, status_text, speed_str="", force=False):
                nonlocal last_report_time, last_bytes_copied
                now = time.time()
                dt = now - last_report_time
                if not force and dt < 0.2:
                    return
                    
                eta_str = ""
                if not speed_str and dt > 0:
                    diff_bytes = copied_bytes - last_bytes_copied
                    current_speed = diff_bytes / dt
                    speed_history.append(current_speed)
                    
                    # Calculate rolling average
                    avg_speed_bps = sum(speed_history) / len(speed_history)
                    
                    speed_mbps = avg_speed_bps / (1024 * 1024)
                    speed_str = f"{speed_mbps:.1f} MB/s"
                    
                    if avg_speed_bps > 0:
                        bytes_left = total_bytes - copied_bytes
                        secs_left = int(bytes_left / avg_speed_bps)
                        if secs_left > 3600:
                            eta_str = f"{secs_left // 3600}h {(secs_left % 3600) // 60}m"
                        elif secs_left > 60:
                            eta_str = f"{secs_left // 60}m {secs_left % 60}s left"
                        else:
                            eta_str = f"{secs_left}s left"
                    else:
                        eta_str = "Calculating..."
                    
                last_report_time = now
                last_bytes_copied = copied_bytes
                
                if webview.windows:
                    safe_text = json.dumps(status_text)
                    safe_speed = json.dumps(speed_str)
                    safe_eta = json.dumps(eta_str)
                    try:
                        webview.windows[0].evaluate_js(f"if(window.updateBackupProgress) window.updateBackupProgress({current_pct}, {safe_text}, {safe_speed}, {safe_eta});")
                    except Exception:
                        pass

            with self._dm.open_device(phone) as wpd:
                for idx, mf in enumerate(files):
                    if self._backup_cancelled:
                        report_progress(100, f"Backup cancelled. {copied_files} files copied.", speed_str="0 MB/s", force=True)
                        return {"success": False, "error": "Cancelled"}
                        
                    while self._backup_paused and not self._backup_cancelled:
                        time.sleep(0.5)
                        
                    if self._backup_cancelled:
                        report_progress(100, f"Backup cancelled. {copied_files} files copied.", speed_str="0 MB/s", force=True)
                        return {"success": False, "error": "Cancelled"}
                    # Construct destination path: dest_dir / relative path on device
                    # E.g. virtual_path = "Internal storage/DCIM/Camera/foo.jpg"
                    # We might want to just keep the original structure
                    safe_rel = mf.virtual_path.replace(":", "_").replace("?", "_")
                    dest_path = os.path.join(dest_dir, safe_rel)
                    
                    # Update UI for current file
                    report_progress((copied_bytes / total_bytes) * 100 if total_bytes else 0, f"Copying {idx+1}/{total_files}: {mf.filename}")
                    
                    # Do the transfer
                    # Simple progress callback for the transfer itself
                    def chunk_cb(bytes_written, file_total):
                        if self._backup_cancelled:
                            return  # Need a way to cancel transfer_file cleanly if we want instant abort
                        pct = ((copied_bytes + bytes_written) / total_bytes) * 100 if total_bytes else 0
                        report_progress(pct, f"Copying {idx+1}/{total_files}: {mf.filename}")
                    
                    def cancel_check():
                        return self._backup_cancelled
                    
                    # Skip if exists and same size (simple duplicate check)
                    if os.path.exists(dest_path) and os.path.getsize(dest_path) == mf.size:
                        copied_bytes += mf.size
                        copied_files += 1
                        continue
                        
                    res = transfer_file(
                        wpd_device=wpd,
                        object_id=mf.object_id,
                        dest_path=dest_path,
                        file_size=mf.size,
                        modified=mf.modified,
                        compute_hash=verify_hash,
                        progress_cb=chunk_cb,
                        cancel_check=cancel_check,
                        chunk_config=app_settings._data
                    )
                    
                    if res.success:
                        if verify_hash and res.sha256_hash:
                            current_pct = ((copied_bytes + mf.size) / total_bytes) * 100 if total_bytes else 0
                            report_progress(current_pct, f"Verifying hash for: {mf.filename}")
                            from app.backup.verifier import verify_copy
                            if not verify_copy(res.sha256_hash, dest_path):
                                logger.error(f"Hash verification failed for {mf.filename}")
                                continue # We don't increment copied_bytes if verification fails
                                
                        copied_bytes += mf.size
                        copied_files += 1
                    else:
                        logger.error(f"Failed to copy {mf.filename}: {res.error}")
            from app.config.settings import HistoryManager
            status_str = "Cancelled" if self._backup_cancelled else "Success"
            HistoryManager.add_entry(device_name, status_str, copied_files)
            
            final_msg = "Backup cancelled!" if self._backup_cancelled else "Backup complete!"
            report_progress(100, f"{final_msg} {copied_files} files copied.", speed_str="Done", force=True)
            return {"success": True, "copied_files": copied_files}
            
        except Exception as e:
            from app.config.settings import HistoryManager
            # We don't have copied_files in scope if it fails before loop, so fallback to 0
            HistoryManager.add_entry(device_name, "Failed", locals().get('copied_files', 0))
            logger.error(f"Backup failed: {e}", exc_info=True)
            return {"success": False, "error": str(e)}
        finally:
            comtypes.CoUninitialize()

    def get_settings(self):
        """Called by JS to load current settings."""
        from app.config.settings import Settings
        s = Settings()
        return {
            "theme": s.theme,
            "backup_dir": s.backup_folder,
            "duplicate_detection": s.duplicate_detection,
            "hash_verification": s.hash_verification,
            "chunk_size_photos_mb": s._data.get("chunk_size_photos_mb", 4),
            "chunk_size_videos_mb": s._data.get("chunk_size_videos_mb", 32),
            "chunk_size_others_mb": s._data.get("chunk_size_others_mb", 1)
        }

    def save_settings(self, settings_data):
        """Called by JS to save settings."""
        try:
            from app.config.settings import Settings
            s = Settings()
            # Only update if provided
            if "theme" in settings_data: s.theme = settings_data["theme"]
            if "backup_dir" in settings_data: s.backup_folder = settings_data["backup_dir"]
            
            # Since duplicate_detection and hash_verification don't have setters yet, we update _data directly
            if "duplicate_detection" in settings_data: s._data["duplicate_detection"] = settings_data["duplicate_detection"]
            if "hash_verification" in settings_data: s._data["hash_verification"] = settings_data["hash_verification"]
            if "chunk_size_photos_mb" in settings_data: s._data["chunk_size_photos_mb"] = settings_data["chunk_size_photos_mb"]
            if "chunk_size_videos_mb" in settings_data: s._data["chunk_size_videos_mb"] = settings_data["chunk_size_videos_mb"]
            if "chunk_size_others_mb" in settings_data: s._data["chunk_size_others_mb"] = settings_data["chunk_size_others_mb"]
            
            s.save()
            return True
        except Exception as e:
            logger.error(f"Error saving settings: {e}")
            return False

    def get_history(self):
        """Returns the real backup history."""
        from app.config.settings import HistoryManager
        return HistoryManager.get_history()

    def choose_folder(self):
        """Opens a native folder picker dialog."""
        import webview
        if webview.windows:
            result = webview.windows[0].create_file_dialog(webview.FOLDER_DIALOG)
            if result and len(result) > 0:
                # Also save it to settings automatically
                from app.config.settings import Settings
                s = Settings()
                s.backup_folder = result[0]
                s.save()
                return result[0]
        return None
