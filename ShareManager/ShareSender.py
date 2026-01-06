import requests
import threading
import os
from requests_toolbelt.multipart.encoder import MultipartEncoder, MultipartEncoderMonitor

class ShareSender:
    def __init__(self, *, timeout=2, sender_id=None, ui_log=None, ui_progress_bar=None, ui_progress_status=None):
        self.timeout = timeout
        self.sender_id = sender_id or "Unknown"
        self.ui_log = ui_log or (lambda *_: None)
        self.ui_progress_bar = ui_progress_bar
        self.ui_progress_status = ui_progress_status

    def _log(self, text):
        self.ui_log(text)

    def _format_bytes(self, bytes_val):
        for unit in ['B', 'KB', 'MB', 'GB']:
            if bytes_val < 1024.0:
                return f"{bytes_val:.1f}{unit}"
            bytes_val /= 1024.0
        return f"{bytes_val:.1f}TB"

    def _update_progress(self, sent, total, peer_name):
        if total <= 0: return
        
        progress_value = sent / total
        percent = progress_value * 100
        
        if self.ui_progress_bar:
            try: self.ui_progress_bar.set(progress_value)
            except: pass
        
        if self.ui_progress_status:
            try:
                status = f"Sending to {peer_name}: {self._format_bytes(sent)}/{self._format_bytes(total)} ({percent:.1f}%)"
                self.ui_progress_status.configure(text=status)
            except: pass

    def send_file(self, peer, file_path: str, max_retries=3) -> bool:
        def _send_file_thread():
            if not os.path.exists(file_path):
                self._log(f"❌ File not found: {file_path}")
                return

            file_size = os.path.getsize(file_path)
            filename = os.path.basename(file_path)
            
            for attempt in range(max_retries):
                try:
                    self._log(f"📁 Attempt {attempt+1}: Sending {filename} ({self._format_bytes(file_size)})")
                    
                    with open(file_path, 'rb') as f:
                        # We use MultipartEncoder for memory-efficient streaming of large files
                        encoder = MultipartEncoder(
                            fields={
                                'sender': self.sender_id,
                                'file': (filename, f, 'application/octet-stream')
                            }
                        )
                        
                        # Monitor tracks the bytes as they flow out of the encoder
                        monitor = MultipartEncoderMonitor(
                            encoder, 
                            lambda m: self._update_progress(m.bytes_read, m.len, peer.name)
                        )

                        # Timeout: 10 mins base + 2 seconds per MB
                        transfer_timeout = max(600, (file_size / (1024 * 1024)) * 2)

                        response = requests.post(
                            f"http://{peer.address}:{peer.port}/upload",
                            data=monitor,
                            headers={'Content-Type': monitor.content_type},
                            timeout=transfer_timeout
                        )

                        if response.status_code == 200 and response.json().get('ok'):
                            self._log(f"✅ Successfully sent to {peer.name}")
                            break
                        else:
                            raise Exception(f"Server Error: {response.text}")

                except Exception as e:
                    self._log(f"⚠️ Attempt {attempt+1} failed: {e}")
                    if attempt == max_retries - 1:
                        self._log(f"❌ Failed to send {filename} after {max_retries} tries.")
                
            self._reset_progress()

        threading.Thread(target=_send_file_thread, daemon=True).start()
        return True

    def _reset_progress(self):
        if self.ui_progress_bar:
            try: self.ui_progress_bar.set(0)
            except: pass
        if self.ui_progress_status:
            try: self.ui_progress_status.configure(text="")
            except: pass