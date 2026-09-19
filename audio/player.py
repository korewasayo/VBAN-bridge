"""Audio player using ffmpeg for MP3 playback over VBAN.

Manages a single ffmpeg subprocess. Only one track plays at a time.
When a new track is requested, the current one is stopped first.
Audio is encoded as VBAN packets and sent to all active destination IPs.
"""
import subprocess
import os
import logging
import socket
import struct
import threading
from typing import Optional
from config import FFPLAY_PATH

logger = logging.getLogger(__name__)


class AudioPlayer:
    """Singleton audio player that streams MP3 via VBAN."""
    _instance: Optional['AudioPlayer'] = None
    _process: Optional[subprocess.Popen] = None
    _thread: Optional[threading.Thread] = None
    _current_file: Optional[str] = None
    _is_playing: bool = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def _vban_emitter(self, file_path: str):
        # We assume FFPLAY_PATH is actually 'ffmpeg' or we just use 'ffmpeg'
        # if the user hasn't overridden it, config.FFPLAY_PATH might be 'ffplay'
        ffmpeg_cmd = "ffmpeg" if "ffplay" in FFPLAY_PATH.lower() else FFPLAY_PATH
        
        cmd = [
            ffmpeg_cmd, "-re", "-i", file_path,
            "-f", "s16le", "-ar", "48000", "-ac", "2", "-loglevel", "quiet", "-"
        ]
        
        try:
            self._process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        except Exception as e:
            logger.error(f"Failed to start ffmpeg: {e}")
            self._is_playing = False
            return
            
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        frame_counter = 0
        stream_name = b"CableAS1".ljust(16, b'\x00')
        
        try:
            import vban_engine
            
            while self._is_playing and self._process.poll() is None:
                pcm_data = self._process.stdout.read(1024)
                if not pcm_data:
                    break
                if len(pcm_data) < 1024:
                    pcm_data = pcm_data.ljust(1024, b'\x00')
                
                # Header for 48000 Hz (index 3), 256 samples, 2 channels, 16-bit
                header = struct.pack('<4sBBBB16sI',
                    b'VBAN', 3, 255, 1, 1, stream_name, frame_counter
                )
                packet = header + pcm_data
                
                # Fetch all unique active destination IPs from vban_engine
                routes = vban_engine.get_routes()
                dest_ips = set()
                for route_list in routes.values():
                    for dest in route_list:
                        if dest.get("active"):
                            dest_ips.add(dest["dest_ip"])
                
                # Send packet to all active destinations
                for dest_ip in dest_ips:
                    try:
                        sock.sendto(packet, (dest_ip, 6980))
                    except Exception:
                        pass
                
                frame_counter += 1
                
        except Exception as e:
            logger.error(f"VBAN emitter error: {e}")
        finally:
            if self._process:
                self._process.terminate()
                self._process.wait(timeout=2)
                self._process = None
            sock.close()
            self._is_playing = False
            self._current_file = None
            logger.info("Playback finished.")

    def play(self, file_path: str) -> bool:
        """Play an MP3 file via VBAN. Stops current playback first.
        Returns True if playback started successfully."""
        if not os.path.exists(file_path):
            logger.error(f"Audio file not found: {file_path}")
            return False
        
        # Stop current playback
        self.stop()
        
        self._current_file = file_path
        self._is_playing = True
        logger.info(f"Now playing (VBAN): {file_path}")
        
        self._thread = threading.Thread(target=self._vban_emitter, args=(file_path,), daemon=True)
        self._thread.start()
        
        return True
    
    def stop(self) -> None:
        """Stop current playback."""
        self._is_playing = False
        if self._process is not None:
            try:
                self._process.terminate()
                self._process.wait(timeout=2)
            except Exception as e:
                try:
                    self._process.kill()
                except:
                    pass
            finally:
                self._process = None
        self._current_file = None
    
    @property
    def is_playing(self) -> bool:
        """Check if audio is currently playing."""
        return self._is_playing
    
    @property
    def current_file(self) -> Optional[str]:
        """Get the currently playing file path."""
        if self.is_playing:
            return self._current_file
        return None
    
    def get_status(self) -> dict:
        """Get current player status."""
        return {
            "is_playing": self.is_playing,
            "current_file": self.current_file
        }


# Global singleton instance
player = AudioPlayer()

