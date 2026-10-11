import subprocess
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


def test_configured_proxy_is_used_for_video_download():
    info = {
        "title": "Video track",
        "webpage_url": "https://youtube.com/watch?v=video123",
        "is_live": False,
    }
    downloader = make_youtube_dl(info)
    with patch("audio.downloader.UPLOAD_DIR", "test-uploads"), patch(
        "audio.downloader.os.makedirs"
    ), patch("audio.downloader.DOWNLOADER_PROXIES", ("http://proxy.example:8080",)), patch(
        "audio.downloader.yt_dlp.YoutubeDL", return_value=downloader
    ) as youtube_dl:
        download_audio_sync(info["webpage_url"])

    assert youtube_dl.call_args.args[0]["proxy"] == "http://proxy.example:8080"


def test_configured_proxy_is_used_for_media_resolution():
    info = {"url": "https://media.example.test/live.m4a"}
    downloader = make_youtube_dl(info)
    with patch("audio.downloader.DOWNLOADER_PROXIES", ("http://proxy.example:8080",)), patch(
        "audio.downloader.yt_dlp.YoutubeDL", return_value=downloader
    ) as youtube_dl:
        extract_media_url("https://example.test/live")

    assert youtube_dl.call_args.args[0]["proxy"] == "http://proxy.example:8080"


def test_configured_proxy_is_passed_to_spotdl():
    with patch("audio.downloader.UPLOAD_DIR", "test-uploads"), patch(
        "audio.downloader.os.makedirs"
    ), patch("audio.downloader.DOWNLOADER_PROXIES", ("http://proxy.example:8080",)), patch(
        "audio.downloader.subprocess.run"
    ) as run, patch("audio.downloader.os.path.exists", return_value=True):
        download_audio_sync("https://open.spotify.com/track/test")

    command = run.call_args.args[0]
    assert command[-2:] == ["--proxy", "http://proxy.example:8080"]


def test_live_media_resolver_returns_headers_for_ffmpeg():
    info = {
        "url": "https://media.example.test/live.m4a",
        "http_headers": {"User-Agent": "test-agent"},
    }
    downloader = make_youtube_dl(info)
    with patch("audio.downloader.yt_dlp.YoutubeDL", return_value=downloader):
        result = extract_media_url("https://example.test/live")

    assert result == info


def test_video_download_switches_to_next_proxy_after_failure():
    info = {
        "title": "Video track",
        "webpage_url": "https://youtube.com/watch?v=video123",
        "is_live": False,
    }
    failed_downloader = make_youtube_dl(info)
    failed_downloader.extract_info.side_effect = RuntimeError("proxy unavailable")
    working_downloader = make_youtube_dl(info)
    with patch("audio.downloader.UPLOAD_DIR", "test-uploads"), patch(
        "audio.downloader.os.makedirs"
    ), patch(
        "audio.downloader.DOWNLOADER_PROXIES",
        ("http://proxy-one.example:8080", "http://proxy-two.example:8080"),
    ), patch(
        "audio.downloader.yt_dlp.YoutubeDL",
        side_effect=[failed_downloader, working_downloader],
    ) as youtube_dl:
        result = download_audio_sync(info["webpage_url"])

    assert result[1] == "Video track"
    assert [call.args[0]["proxy"] for call in youtube_dl.call_args_list] == [
        "http://proxy-one.example:8080",
        "http://proxy-two.example:8080",
    ]


def test_media_resolution_switches_to_next_proxy_after_failure():
    info = {"url": "https://media.example.test/live.m4a"}
    failed_downloader = make_youtube_dl(info)
    failed_downloader.extract_info.side_effect = RuntimeError("proxy unavailable")
    working_downloader = make_youtube_dl(info)
    with patch(
        "audio.downloader.DOWNLOADER_PROXIES",
        ("http://proxy-one.example:8080", "http://proxy-two.example:8080"),
    ), patch(
        "audio.downloader.yt_dlp.YoutubeDL",
        side_effect=[failed_downloader, working_downloader],
    ) as youtube_dl:
        result = extract_media_url("https://example.test/live")

    assert result["proxy"] == "http://proxy-two.example:8080"
    assert [call.args[0]["proxy"] for call in youtube_dl.call_args_list] == [
        "http://proxy-one.example:8080",
        "http://proxy-two.example:8080",
    ]


def test_spotdl_switches_to_next_proxy_after_failure():
    failed = subprocess.CalledProcessError(1, "spotdl", stderr="proxy unavailable")
    with patch("audio.downloader.UPLOAD_DIR", "test-uploads"), patch(
        "audio.downloader.os.makedirs"
    ), patch(
        "audio.downloader.DOWNLOADER_PROXIES",
        ("http://proxy-one.example:8080", "http://proxy-two.example:8080"),
    ), patch("audio.downloader.subprocess.run", side_effect=[failed, None]) as run, patch(
        "audio.downloader.os.path.exists", return_value=True
    ):
        download_audio_sync("https://open.spotify.com/track/test")

    assert [call.args[0][-2:] for call in run.call_args_list] == [
        ["--proxy", "http://proxy-one.example:8080"],
        ["--proxy", "http://proxy-two.example:8080"],
    ]
