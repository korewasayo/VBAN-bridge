import os
import asyncio
import logging
import uuid
import subprocess
import sys
from typing import Optional, Tuple
import yt_dlp

from config import UPLOAD_DIR, FFMPEG_LOCATION
from database.db import execute_query
from database.models import add_audit_log

logger = logging.getLogger(__name__)


def extract_media_url(source_url: str) -> dict:
    """Resolve a webpage URL to a temporary media URL and its required headers."""
    opts = {
        'format': 'bestaudio/best',
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
        'retries': 3,
        'extractor_retries': 3,
        'socket_timeout': 20,
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(source_url, download=False)
    if info and 'entries' in info:
        info = next((entry for entry in info['entries'] if entry), None)
    if not info or not info.get('url'):
        raise ValueError("The video or live stream has no playable audio source.")
    return {
        'url': info['url'],
        'http_headers': info.get('http_headers') or {},
    }


async def download_audio_task(query: str, request_id: int, user_id: Optional[int], ip: str):
    """Background task to download audio from a query or URL."""
    try:
        # Mark as pending initially (this is done in the route before spawning task)
        
        # Download audio
        mp3_path, title, artist, thumbnail_url, source_url = await asyncio.to_thread(download_audio_sync, query)
        
        # If no thumbnail URL was returned, try to extract APIC from MP3
        if mp3_path and not thumbnail_url:
            try:
                from mutagen.mp3 import MP3
                from mutagen.id3 import ID3, APIC
                audio = MP3(mp3_path, ID3=ID3)
                if audio.tags:
                    for tag in audio.tags.values():
                        if isinstance(tag, APIC):
                            os.makedirs("static/thumbnails", exist_ok=True)
                            thumb_path = f"static/thumbnails/{request_id}.jpg"
                            with open(thumb_path, "wb") as img:
                                img.write(tag.data)
                            thumbnail_url = f"/static/thumbnails/{request_id}.jpg"
                            break
            except Exception as e:
                logger.warning(f"Could not extract thumbnail from {mp3_path}: {e}")

        # Update database with the new mp3 path, title, artist
        if source_url:
            await execute_query(
                "UPDATE music_requests SET source_url = ?, title = ?, artist = ?, thumbnail_url = ?, duration_seconds = 0 WHERE id = ?",
                (source_url, title, artist, thumbnail_url, request_id)
            )
            logger.info(f"Prepared live stream request {request_id}: {source_url}")
        elif mp3_path:
            await execute_query(
                "UPDATE music_requests SET mp3_path = ?, title = ?, artist = ?, thumbnail_url = ? WHERE id = ?",
                (mp3_path, title, artist, thumbnail_url, request_id)
            )
            logger.info(f"Successfully downloaded request {request_id} to {mp3_path}")
        else:
            raise Exception("Download completed but no file path returned.")
            
    except Exception as e:
        logger.error(f"Failed to download audio for request {request_id}: {e}")
        error_msg = str(e)
        if "video unavailable" in error_msg.lower():
            error_msg = (
                "YouTube reports this video as unavailable to the server. Check that it still plays in a browser "
                "and is not private, deleted, or region-restricted. Updating yt-dlp may help with temporary extractor issues."
            )
        # Set status to rejected with the error message
        await execute_query(
            "UPDATE music_requests SET status = 'rejected', reject_reason = ? WHERE id = ?",
            (f"Download failed: {error_msg}", request_id)
        )
        await add_audit_log(user_id, "download_failed", f"Failed to download request {request_id}: {error_msg}", ip)

def download_audio_sync(query: str) -> Tuple[Optional[str], str, str, str, Optional[str]]:
    """
    Downloads audio using yt-dlp or spotdl.
    Returns (mp3_path, title, artist, thumbnail_url, live_source_url).
    Exactly one of mp3_path and live_source_url is populated on success.
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
                [sys.executable, "-m", "spotdl", query, "--output", output_template_spotdl, "--format", "mp3"],
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
                return final_path, "Spotify Download", "", "", None
            else:
                # Try to find any file that starts with file_id
                for f in os.listdir(UPLOAD_DIR):
                    if f.startswith(file_id) and f.endswith(".mp3"):
                        return os.path.join(UPLOAD_DIR, f), "Spotify Download", "", "", None
                raise Exception("spotdl finished but file not found.")
        except subprocess.CalledProcessError as e:
            logger.error(f"spotdl failed: {e.stderr}")
            raise Exception(f"Failed to download from Spotify: {e.stderr.strip()}")
            
    # For YouTube, SoundCloud, or Text Search, use yt-dlp
    ydl_opts = {
        'format': 'bestaudio/best',
        'ffmpeg_location': FFMPEG_LOCATION,
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'outtmpl': output_template,
        'quiet': True,
        'no_warnings': True,
        'default_search': 'ytsearch',
        'retries': 3,
        'fragment_retries': 3,
        'extractor_retries': 3,
        'socket_timeout': 20,
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info_dict = ydl.extract_info(query, download=False)
        if 'entries' in info_dict:
            # It was a playlist or search, take the first item
            info_dict = next((entry for entry in info_dict['entries'] if entry), None)
            if not info_dict:
                raise Exception("No results found.")

        title = info_dict.get('title', 'Unknown Title')
        artist = info_dict.get('uploader', info_dict.get('artist', 'Unknown Artist'))
        thumbnail = info_dict.get('thumbnail', '')
        live_status = info_dict.get('live_status')
        if live_status == 'is_upcoming':
            raise ValueError("This live stream has not started yet. Request it again after the broadcast begins.")
        if info_dict.get('is_live') or live_status == 'is_live':
            live_url = info_dict.get('webpage_url') or query
            return None, title, artist, thumbnail, live_url

        video_url = info_dict.get('webpage_url') or query
        ydl.download([video_url])
        
        # Determine the final path (yt-dlp replaces %(ext)s with mp3 after postprocessing)
        final_path = os.path.join(UPLOAD_DIR, f"{file_id}.mp3")
        
        return final_path, title, artist, thumbnail, None
