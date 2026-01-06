import requests
import threading
import os


class ShareSender:
    def __init__(self, *, timeout=2, sender_id=None, ui_log=None, ui_progress_bar=None, ui_progress_status=None):
        self.timeout = timeout
        self.sender_id = sender_id
        self.ui_log = ui_log or (lambda *_: None)
        self.ui_progress_bar = ui_progress_bar
        self.ui_progress_status = ui_progress_status

    def _log(self, text):
        """Log message to UI"""
        self.ui_log(text)

    def connect_peer(self, peer) -> bool:
        """Test connection to a peer"""
        try:
            requests.get(
                f"http://{peer.address}:{peer.port}/ping",
                timeout=self.timeout,
            )
            self._log(f"✅ Connected to {peer.name}")
            return True
        except Exception as e:
            self._log(f"❌ Connect failed {peer.name}: {e}")
            return False

    def send_message(self, peer, message: str) -> bool:
        """Send a text message to a peer"""
        try:
            requests.post(
                f"http://{peer.address}:{peer.port}/message",
                json={
                    "sender": self.sender_id,
                    "message": message,
                },
                timeout=self.timeout,
            )
            self._log(f"📤 Sent to {peer.name}")
            return True
        except Exception as e:
            self._log(f"❌ Send failed {peer.name}: {e}")
            return False

    def send_file(self, peer, file_path: str, max_retries=3) -> bool:
        """Send a file to a peer asynchronously with progress tracking"""
        result = {'success': False}

        def _send_file_thread():
            retries = 0
            
            while retries < max_retries:
                try:
                    if not os.path.exists(file_path):
                        self._log(f"❌ File not found: {file_path}")
                        return
                    
                    file_size = os.path.getsize(file_path)
                    filename = os.path.basename(file_path)
                    
                    self._log(f"📁 Sending file to {peer.name}: {filename} ({self._format_bytes(file_size)})")
                    
                    with open(file_path, 'rb') as f:
                        progress_file = ProgressFileWrapper(
                            f,
                            file_size,
                            lambda sent, total: self._update_progress(sent, total, peer.name)
                        )
                        
                        files = {
                            'file': (filename, progress_file, 'application/octet-stream')
                        }
                        data = {
                            'sender': self.sender_id
                        }
                        
                        transfer_timeout = max(60, (file_size / (1024 * 100)) + 30)
                        
                        response = requests.post(
                            f"http://{peer.address}:{peer.port}/upload",
                            files=files,
                            data=data,
                            timeout=transfer_timeout
                        )
                        
                        if response.status_code == 200:
                            response_data = response.json()
                            if response_data.get('ok'):
                                self._log(f"✅ File sent successfully to {peer.name}: {filename}")
                                result['success'] = True
                                break
                            else:
                                raise Exception(f"Server returned ok=False: {response_data}")
                        else:
                            raise Exception(f"HTTP {response.status_code}: {response.text}")
                
                except FileNotFoundError:
                    self._log(f"❌ File not found: {file_path}")
                    break
                
                except requests.exceptions.Timeout:
                    retries += 1
                    if retries < max_retries:
                        self._log(f"⚠️ Transfer timed out. Retry {retries}/{max_retries}...")
                    else:
                        self._log(f"❌ Transfer failed after {max_retries} attempts: Timeout")
                
                except requests.exceptions.ConnectionError as e:
                    retries += 1
                    if retries < max_retries:
                        self._log(f"⚠️ Connection error. Retry {retries}/{max_retries}...")
                    else:
                        self._log(f"❌ Transfer failed after {max_retries} attempts: {e}")
                
                except Exception as e:
                    retries += 1
                    if retries < max_retries:
                        self._log(f"⚠️ Error: {e}. Retry {retries}/{max_retries}...")
                    else:
                        self._log(f"❌ File send failed to {peer.name}: {e}")
                
                finally:
                    if retries >= max_retries or result['success']:
                        self._reset_progress()

        thread = threading.Thread(target=_send_file_thread, daemon=True)
        thread.start()
        
        return True

    def _update_progress(self, sent, total, peer_name):
        """Update UI with transfer progress"""
        if total == 0:
            return
        
        percent = (sent / total) * 100
        progress_value = sent / total
        
        if self.ui_progress_bar:
            try:
                self.ui_progress_bar.set(progress_value)
            except:
                pass
        
        if self.ui_progress_status:
            try:
                progress_text = (
                    f"Sending to {peer_name}: "
                    f"{self._format_bytes(sent)}/{self._format_bytes(total)} "
                    f"({percent:.1f}%)"
                )
                self.ui_progress_status.configure(text=progress_text)
            except:
                pass

    def _reset_progress(self):
        """Reset progress bar and status after transfer completes"""
        if self.ui_progress_bar:
            try:
                self.ui_progress_bar.set(0)
            except:
                pass
        
        if self.ui_progress_status:
            try:
                self.ui_progress_status.configure(text="")
            except:
                pass

    def _format_bytes(self, bytes_val):
        """Format bytes to human-readable string"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if bytes_val < 1024.0:
                return f"{bytes_val:.1f}{unit}"
            bytes_val /= 1024.0
        return f"{bytes_val:.1f}TB"


class ProgressFileWrapper:
    """Wrapper for file objects that tracks read progress"""
    
    def __init__(self, file_obj, total_size, callback):
        self.file_obj = file_obj
        self.total_size = total_size
        self.callback = callback
        self.sent = 0
    
    def read(self, size=-1):
        """Read from file and track progress"""
        chunk = self.file_obj.read(size)
        
        if chunk:
            self.sent += len(chunk)
            self.callback(self.sent, self.total_size)
        
        return chunk
    
    def __len__(self):
        """Return total file size"""
        return self.total_size