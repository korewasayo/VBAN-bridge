import os
import asyncio
import logging
import uuid
import subprocess
import sys
from typing import Optional, Tuple
import yt_dlp

from config import UPLOAD_DIR, FFMPEG_LOCATION, DOWNLOADER_PROXIES
from database.db import execute_query
from database.models import add_audit_log

logger = logging.getLogger(__name__)


def _proxy_attempts():
    return DOWNLOADER_PROXIES or (None,)


def extract_media_url(source_url: str) -> dict:
    """Resolve a webpage URL to a temporary media URL and its required headers."""
    last_error = None
    for proxy in _proxy_attempts():
        opts = {
            'format': 'bestaudio/best',
            'noplaylist': True,
            'quiet': True,
            'no_warnings': True,
            'retries': 3,
            'extractor_retries': 3,
            'socket_timeout': 20,
        }
        if proxy:
            opts['proxy'] = proxy
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(source_url, download=False)
            if info and 'entries' in info:
                info = next((entry for entry in info['entries'] if entry), None)
            if not info or not info.get('url'):
                raise ValueError("The video or live stream has no playable audio source.")
            media = {
                'url': info['url'],
                'http_headers': info.get('http_headers') or {},
            }
            if proxy:
                media['proxy'] = proxy
            return media
        except Exception as error:
            last_error = error
            logger.warning("Media URL resolution failed through proxy %s: %s", proxy or "direct", error)
    raise last_error


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
        last_error = None
        for proxy in _proxy_attempts():
            spotdl_command = [
                sys.executable, "-m", "spotdl", query, "--output", output_template_spotdl, "--format", "mp3"
            ]
            if proxy:
                spotdl_command.extend(["--proxy", proxy])
            try:
                subprocess.run(spotdl_command, capture_output=True, text=True, check=True)
                final_path = os.path.join(UPLOAD_DIR, f"{file_id}.mp3")
                if os.path.exists(final_path):
                    return final_path, "Spotify Download", "", "", None
                for filename in os.listdir(UPLOAD_DIR):
                    if filename.startswith(file_id) and filename.endswith(".mp3"):
                        return os.path.join(UPLOAD_DIR, filename), "Spotify Download", "", "", None
                raise RuntimeError("spotdl finished but file not found.")
            except Exception as error:
                last_error = error
                logger.warning("spotdl failed through proxy %s: %s", proxy or "direct", error)
        if isinstance(last_error, subprocess.CalledProcessError):
            raise Exception(f"Failed to download from Spotify: {last_error.stderr.strip()}") from last_error
        raise last_error
            
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
    last_error = None
    for proxy in _proxy_attempts():
        opts = dict(ydl_opts)
        if proxy:
            opts['proxy'] = proxy
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info_dict = ydl.extract_info(query, download=False)
                if 'entries' in info_dict:
                    info_dict = next((entry for entry in info_dict['entries'] if entry), None)
                    if not info_dict:
                        raise ValueError("No results found.")

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

            final_path = os.path.join(UPLOAD_DIR, f"{file_id}.mp3")
            return final_path, title, artist, thumbnail, None
        except ValueError:
            raise
        except Exception as error:
            last_error = error
            logger.warning("Audio download failed through proxy %s: %s", proxy or "direct", error)
    raise last_error
