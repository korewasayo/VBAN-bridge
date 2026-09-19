"""Audio player using ffplay for MP3 playback.

Manages a single ffplay subprocess. Only one track plays at a time.
When a new track is requested, the current one is stopped first.
"""
import subprocess
import os
import logging
from typing import Optional
from config import FFPLAY_PATH

logger = logging.getLogger(__name__)


class AudioPlayer:
    """Singleton audio player that manages ffplay subprocess."""
    _instance: Optional['AudioPlayer'] = None
    _process: Optional[subprocess.Popen] = None
    _current_file: Optional[str] = None
    _is_playing: bool = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def play(self, file_path: str) -> bool:
        """Play an MP3 file. Stops current playback first.
        Returns True if playback started successfully."""
        if not os.path.exists(file_path):
            logger.error(f"Audio file not found: {file_path}")
            return False
        
        # Stop current playback
        self.stop()
        
        try:
            # ffplay flags:
            # -nodisp: no video display window
            # -autoexit: exit when done playing
            # -loglevel quiet: suppress ffplay output
            self._process = subprocess.Popen(
                [FFPLAY_PATH, "-nodisp", "-autoexit", "-loglevel", "quiet", file_path],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            self._current_file = file_path
            self._is_playing = True
            logger.info(f"Now playing: {file_path}")
            return True
        except FileNotFoundError:
            logger.error(f"ffplay not found at: {FFPLAY_PATH}. Install ffmpeg or set FFPLAY_PATH.")
            return False
        except Exception as e:
            logger.error(f"Failed to start playback: {e}")
            return False
    
    def stop(self) -> None:
        """Stop current playback."""
        if self._process is not None:
            try:
                self._process.terminate()
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()
                self._process.wait()
            except Exception as e:
                logger.error(f"Error stopping playback: {e}")
            finally:
                self._process = None
                self._current_file = None
                self._is_playing = False
    
    @property
    def is_playing(self) -> bool:
        """Check if audio is currently playing."""
        if self._process is not None:
            # Check if process is still running
            poll = self._process.poll()
            if poll is not None:
                # Process has ended
                self._is_playing = False
                self._process = None
                self._current_file = None
                return False
            return True
        return False
    
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
