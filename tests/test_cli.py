import pytest

from event_report import cli, config, youtube


@pytest.fixture
def project(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "ROOT", tmp_path)
    monkeypatch.setattr(config, "ENV_PATH", tmp_path / ".env")
    monkeypatch.setattr(config, "VIDEO_DIR", tmp_path / "動画フォルダ")
    monkeypatch.setattr(config, "REPORT_DIR", tmp_path / "レポート出力")
    monkeypatch.setattr(config, "WRITING_GUIDE_PATH", tmp_path / "レポートの書き方.md")
    monkeypatch.setenv("ELEVENLABS_API_KEY", "el-key")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "an-key")
    return tmp_path


def test_youtube_mode_asks_names_up_front_then_processes_each_url(project, monkeypatch, capsys):
    titles = {"https://youtu.be/one": "春の交流会", "https://youtu.be/private": None}

    def fake_fetch_title(url):
        if titles[url] is None:
            raise youtube.YouTubeError("この動画は「非公開」のため読み込めません。")
        return titles[url]

    answers = iter([
        "https://youtu.be/one",
        "https://www.facebook.com/videos/1",
        "https://youtu.be/private",
        "",            # URL入力の終わり
        "春交流会2026",  # 1本目のレポート名
    ])
    processed = []

    def fake_process_url(url, name, settings, report_root, guide, memo_dir, force=False):
        processed.append((url, name, settings.anthropic_api_key, memo_dir))
        path = report_root / name / "レポート.md"
        path.parent.mkdir(parents=True)
        path.write_text("# r", encoding="utf-8")
        return path

    monkeypatch.setattr("builtins.input", lambda prompt="": next(answers))
    monkeypatch.setattr(cli.youtube, "fetch_title", fake_fetch_title)
    monkeypatch.setattr(cli, "process_url", fake_process_url)

    assert cli.main(["--youtube"]) == 0

    assert processed == [("https://youtu.be/one", "春交流会2026", "an-key", config.VIDEO_DIR)]
    out = capsys.readouterr().out
    assert "YouTubeのURLではないためスキップします: https://www.facebook.com/videos/1" in out
    assert "非公開" in out
    assert "完成: レポート出力/春交流会2026/レポート.md" in out.replace("\\", "/")


def test_url_option_uses_youtube_title_without_prompting(project, monkeypatch):
    processed = []
    monkeypatch.setattr("builtins.input", lambda prompt="": pytest.fail("should not prompt"))
    monkeypatch.setattr(cli.youtube, "fetch_title", lambda url: "春の交流会: 第1部")
    monkeypatch.setattr(cli, "process_url", lambda url, name, *a, **k: processed.append(name))

    assert cli.main(["--url", "https://youtu.be/one"]) == 0
    assert processed == ["春の交流会_ 第1部"]
