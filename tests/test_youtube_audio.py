import functools
import http.server
import subprocess
import threading

import imageio_ffmpeg
import pytest

from event_report import cli, config, youtube


def make_video(path, seconds=3):
    subprocess.run([
        imageio_ffmpeg.get_ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-y",
        "-f", "lavfi", "-i", "testsrc=size=160x120:rate=5",
        "-f", "lavfi", "-i", "sine=frequency=440",
        "-t", str(seconds), "-c:v", "libx264", "-c:a", "aac", str(path),
    ], check=True)


def probe(path):
    """ffmpeg -i の出力からコーデックと長さを読む(ffprobeは同梱されていないため)。"""
    result = subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-hide_banner", "-i", str(path)], capture_output=True, text=True)
    return result.stderr


@pytest.fixture
def local_server(tmp_path):
    served = tmp_path / "served"
    served.mkdir()
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(served))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield served, f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


def test_download_audio_saves_mp3_named_after_title_without_overwriting(local_server, tmp_path):
    served, base_url = local_server
    make_video(served / "spring_event.mp4")
    dest = tmp_path / "音声フォルダ"
    dest.mkdir()

    first = youtube.download_audio(f"{base_url}/spring_event.mp4", dest)
    second = youtube.download_audio(f"{base_url}/spring_event.mp4", dest)

    assert first == dest / "spring_event.mp3"
    assert second == dest / "spring_event (2).mp3"
    info = probe(first)
    assert "Audio: mp3" in info
    assert "mono" in info
    assert "Video:" not in info
    assert "Duration: 00:00:03" in info or "Duration: 00:00:02" in info
    # 一時ファイル(ダウンロードした元の動画)は残らない
    assert sorted(p.name for p in dest.iterdir()) == ["spring_event (2).mp3", "spring_event.mp3"]


class FakeYoutubeDL:
    info = {}

    def __init__(self, options):
        self.options = options

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def extract_info(self, url, download):
        return dict(self.info)

    def process_ie_result(self, info, download):
        raise AssertionError("配信中/準備中の動画はダウンロードしてはいけない")


@pytest.mark.parametrize("live_status, message", [
    ("is_live", "配信中"),
    ("is_upcoming", "まだ始まっていません"),
    ("post_live", "準備中"),
])
def test_download_audio_refuses_streams_that_are_not_finished(monkeypatch, tmp_path, live_status, message):
    FakeYoutubeDL.info = {"title": "t", "live_status": live_status}
    monkeypatch.setattr(youtube, "YoutubeDL", FakeYoutubeDL)

    with pytest.raises(youtube.YouTubeError, match=message):
        youtube.download_audio("https://youtu.be/abc", tmp_path)


def test_download_audio_passes_bundled_deno_to_yt_dlp(monkeypatch, tmp_path):
    captured = {}

    class Capture(FakeYoutubeDL):
        def __init__(self, options):
            captured.update(options)
            raise youtube.YouTubeError("stop")

    monkeypatch.setattr(youtube, "YoutubeDL", Capture)
    with pytest.raises(youtube.YouTubeError):
        youtube.download_audio("https://youtu.be/abc", tmp_path)

    deno_path = captured["js_runtimes"]["deno"]["path"]
    assert subprocess.run([deno_path, "--version"], capture_output=True, text=True).stdout.startswith("deno ")
    assert captured["noplaylist"] is True


@pytest.mark.parametrize("raw, expected", [
    ("ERROR: [youtube] abc: Private video. Sign in if you've been granted access", "非公開"),
    ("ERROR: [youtube] abc: Sign in to confirm you're not a bot", "制限"),
    ("ERROR: [youtube] abc: Video unavailable", "見つかりません"),
    ("ERROR: [youtube] abc: Unable to download API page: ('Unable to connect to proxy', OSError('Tunnel connection failed: 403 Forbidden'))", "インターネット接続"),
    ("ERROR: [youtube] abc: Unable to download API page: <urlopen error [Errno 11001] getaddrinfo failed>", "インターネット接続"),
    ("ERROR: something else", "something else"),
])
def test_describe_download_error(raw, expected):
    assert expected in youtube._describe_download_error(raw)


@pytest.fixture
def project_without_keys(tmp_path, monkeypatch):
    for name in ["ROOT", "ENV_PATH", "VIDEO_DIR", "REPORT_DIR", "AUDIO_DIR", "WRITING_GUIDE_PATH"]:
        default = getattr(config, name)
        monkeypatch.setattr(config, name, tmp_path if name == "ROOT" else tmp_path / default.name)
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    return tmp_path


def test_audio_mode_works_without_api_keys(project_without_keys, monkeypatch, capsys):
    saved = []

    def fake_download(url, dest_dir):
        path = dest_dir / "春の交流会.mp3"
        path.write_bytes(b"mp3")
        saved.append((url, dest_dir))
        return path

    answers = iter(["https://youtube.com/live/abc?feature=share", "https://example.com/x.mp4", ""])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(answers))
    monkeypatch.setattr(cli.youtube, "download_audio", fake_download)

    assert cli.main(["--youtube-audio"]) == 0

    assert saved == [("https://youtube.com/live/abc?feature=share", config.AUDIO_DIR)]
    out = capsys.readouterr().out.replace("\\", "/")
    assert "YouTubeのURLではないためスキップします: https://example.com/x.mp4" in out
    assert "完成: 音声フォルダ/春の交流会.mp3" in out


def test_audio_mode_reports_youtube_errors_plainly(project_without_keys, monkeypatch, capsys):
    def fail(url, dest_dir):
        raise youtube.YouTubeError("この動画は配信中です。配信が終わってから実行してください。")

    monkeypatch.setattr(cli.youtube, "download_audio", fail)

    assert cli.main(["--audio-url", "https://youtu.be/abc"]) == 1
    assert "× 失敗しました: この動画は配信中です。" in capsys.readouterr().out


def test_setup_lets_staff_skip_api_keys(project_without_keys, monkeypatch, capsys):
    monkeypatch.setattr("builtins.input", lambda prompt="": "")

    assert cli.main(["--setup"]) == 0

    assert config.AUDIO_DIR.is_dir()
    assert config.ENV_PATH.read_text() == ""
    assert "セットアップが完了しました" in capsys.readouterr().out
