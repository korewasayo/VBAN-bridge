from unittest.mock import MagicMock, patch

from audio.downloader import download_audio_sync, extract_media_url


def make_youtube_dl(info):
    downloader = MagicMock()
    downloader.__enter__.return_value = downloader
    downloader.extract_info.return_value = info
    return downloader


def test_active_live_source_is_queued_without_downloading():
    info = {
        "title": "Live broadcast",
        "uploader": "Station",
        "thumbnail": "https://example.test/thumb.jpg",
        "webpage_url": "https://youtube.com/watch?v=live123",
        "is_live": True,
        "live_status": "is_live",
    }
    downloader = make_youtube_dl(info)
    with patch("audio.downloader.yt_dlp.YoutubeDL", return_value=downloader):
        result = download_audio_sync(info["webpage_url"])

    assert result == (None, "Live broadcast", "Station", info["thumbnail"], info["webpage_url"])
    downloader.download.assert_not_called()


def test_video_source_is_downloaded_as_audio():
    info = {
        "title": "Video track",
        "uploader": "Artist",
        "webpage_url": "https://youtube.com/watch?v=video123",
        "is_live": False,
    }
    downloader = make_youtube_dl(info)
    with patch("audio.downloader.UPLOAD_DIR", "test-uploads"), patch(
        "audio.downloader.os.makedirs"
    ), patch("audio.downloader.yt_dlp.YoutubeDL", return_value=downloader):
        path, title, artist, thumbnail, source_url = download_audio_sync(info["webpage_url"])

    assert path.endswith(".mp3")
    assert title == "Video track"
    assert artist == "Artist"
    assert thumbnail == ""
    assert source_url is None
    downloader.download.assert_called_once_with([info["webpage_url"]])


def test_live_media_resolver_returns_headers_for_ffmpeg():
    info = {
        "url": "https://media.example.test/live.m4a",
        "http_headers": {"User-Agent": "test-agent"},
    }
    downloader = make_youtube_dl(info)
    with patch("audio.downloader.yt_dlp.YoutubeDL", return_value=downloader):
        result = extract_media_url("https://example.test/live")

    assert result == info
