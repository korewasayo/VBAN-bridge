import os
import asyncio
import logging
import uuid
import subprocess
from typing import Optional, Tuple
import yt_dlp

from config import UPLOAD_DIR
from database.db import execute_query
from database.models import add_audit_log

logger = logging.getLogger(__name__)

async def download_audio_task(query: str, request_id: int, user_id: Optional[int], ip: str):
    """Background task to download audio from a query or URL."""
    try:
        # Mark as pending initially (this is done in the route before spawning task)
        
        # Download audio
        mp3_path, title, artist = await asyncio.to_thread(download_audio_sync, query)
        
        # Update database with the new mp3 path, title, artist
        if mp3_path:
            await execute_query(
                "UPDATE music_requests SET mp3_path = ?, title = ?, artist = ? WHERE id = ?",
                (mp3_path, title, artist, request_id)
            )
            logger.info(f"Successfully downloaded request {request_id} to {mp3_path}")
        else:
            raise Exception("Download completed but no file path returned.")
            
    except Exception as e:
        logger.error(f"Failed to download audio for request {request_id}: {e}")
        error_msg = str(e)
        # Set status to rejected with the error message
        await execute_query(
            "UPDATE music_requests SET status = 'rejected', reject_reason = ? WHERE id = ?",
            (f"Download failed: {error_msg}", request_id)
        )
        await add_audit_log(user_id, "download_failed", f"Failed to download request {request_id}: {error_msg}", ip)

def download_audio_sync(query: str) -> Tuple[str, str, str]:
    """
    Downloads audio using yt-dlp or spotdl.
    Returns a tuple of (file_path, title, artist).
    Runs synchronously (meant to be run in a thread).
    """
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    file_id = str(uuid.uuid4())
    output_template = os.path.join(UPLOAD_DIR, f"{file_id}.%(ext)s")
    
    # Check if it's a Spotify link
    if "spotify.com" in query:
        # Use spotdl via subprocess
        # spotdl saves to current directory by default, we can pass --output
        output_template_spotdl = os.path.join(UPLOAD_DIR, f"{file_id}.{{ext}}")
        try:
            # We use subprocess to run spotdl module
            result = subprocess.run(
                ["venv\\Scripts\\python", "-m", "spotdl", query, "--output", output_template_spotdl, "--format", "mp3"],
                capture_output=True,
                text=True,
                check=True
            )
            # Find the downloaded file. It should be {file_id}.mp3
            final_path = os.path.join(UPLOAD_DIR, f"{file_id}.mp3")
            if os.path.exists(final_path):
                # We can't easily extract title/artist from spotdl stdout without parsing,
                # but we can just use the query as title for now or parse the filename if we had used default naming.
                # Since we specified output, we'll just return generic title.
                return final_path, "Spotify Download", ""
            else:
                # Try to find any file that starts with file_id
                for f in os.listdir(UPLOAD_DIR):
                    if f.startswith(file_id) and f.endswith(".mp3"):
                        return os.path.join(UPLOAD_DIR, f), "Spotify Download", ""
                raise Exception("spotdl finished but file not found.")
        except subprocess.CalledProcessError as e:
            logger.error(f"spotdl failed: {e.stderr}")
            raise Exception(f"Failed to download from Spotify: {e.stderr.strip()}")
            
    # For YouTube, SoundCloud, or Text Search, use yt-dlp
    ydl_opts = {
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'outtmpl': output_template,
        'quiet': True,
        'no_warnings': True,
        'default_search': 'ytsearch',
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info_dict = ydl.extract_info(query, download=True)
        if 'entries' in info_dict:
            # It was a playlist or search, take the first item
            if len(info_dict['entries']) > 0:
                info_dict = info_dict['entries'][0]
            else:
                raise Exception("No results found.")
        
        # Determine the final path (yt-dlp replaces %(ext)s with mp3 after postprocessing)
        final_path = os.path.join(UPLOAD_DIR, f"{file_id}.mp3")
        
        title = info_dict.get('title', 'Unknown Title')
        artist = info_dict.get('uploader', info_dict.get('artist', 'Unknown Artist'))
        
        return final_path, title, artist
