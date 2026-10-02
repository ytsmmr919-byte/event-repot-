import httpx
import pytest

from event_report import youtube


@pytest.mark.parametrize("url, expected", [
    ("https://www.youtube.com/watch?v=abc123", True),
    ("https://youtube.com/live/abc123?si=x", True),
    ("https://youtu.be/abc123", True),
    (" https://m.youtube.com/watch?v=abc123 ", True),
    ("https://www.facebook.com/videos/123", False),
    ("youtube.com/watch?v=abc123", False),
    ("https://notyoutube.com/watch?v=abc123", False),
])
def test_is_youtube_url(url, expected):
    assert youtube.is_youtube_url(url) is expected


def test_to_folder_name_removes_forbidden_characters_and_truncates():
    assert youtube.to_folder_name('【LIVE】春の交流会: 第1部/第2部 "Q&A"?') == "【LIVE】春の交流会_ 第1部_第2部 _Q&A__"
    assert len(youtube.to_folder_name("あ" * 100)) == youtube.MAX_NAME_LENGTH
    assert youtube.to_folder_name(" ... ") == "YouTube動画"


def fake_get(status, payload=None):
    def get(url, params, timeout, follow_redirects):
        assert url == youtube.OEMBED_URL
        assert params == {"url": "https://youtu.be/abc", "format": "json"}
        return httpx.Response(status, json=payload or {}, request=httpx.Request("GET", url))
    return get


def test_fetch_title(monkeypatch):
    monkeypatch.setattr(youtube.httpx, "get", fake_get(200, {"title": "春の交流会"}))
    assert youtube.fetch_title("https://youtu.be/abc") == "春の交流会"


@pytest.mark.parametrize("status, message", [(401, "非公開"), (403, "非公開"), (404, "見つかりません")])
def test_fetch_title_reports_private_or_missing_video(monkeypatch, status, message):
    monkeypatch.setattr(youtube.httpx, "get", fake_get(status))
    with pytest.raises(youtube.YouTubeError, match=message):
        youtube.fetch_title("https://youtu.be/abc")
