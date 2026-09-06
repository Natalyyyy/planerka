import pytest
from pathlib import Path
from planerka.runner.assemble import assemble


@pytest.fixture
def blocks(tmp_path):
    (tmp_path / "sources").mkdir(parents=True)
    (tmp_path / "platforms").mkdir()
    (tmp_path / "core.md").write_text("ЯДРО", encoding="utf-8")
    (tmp_path / "sources" / "транскрипты.md").write_text("ТРАНСКРИПТЫ", encoding="utf-8")
    (tmp_path / "sources" / "чаты.md").write_text("ЧАТЫ", encoding="utf-8")
    (tmp_path / "platforms" / "телеграм.md").write_text("ТЕЛЕГРАМ", encoding="utf-8")
    return tmp_path


def _и(*имена):
    return [{"имя": и} for и in имена]


def test_складывает_ядро_источники_и_площадки(blocks):
    out = assemble({"источники": _и("транскрипты"), "площадки": ["телеграм"]}, blocks)
    assert out.index("ЯДРО") < out.index("ТРАНСКРИПТЫ") < out.index("ТЕЛЕГРАМ")


def test_неподключённый_источник_не_упомянут(blocks):
    out = assemble({"источники": _и("транскрипты"), "площадки": ["телеграм"]}, blocks)
    assert "ЧАТЫ" not in out


def test_без_источников_остаётся_одно_ядро(blocks):
    out = assemble({"источники": [], "площадки": []}, blocks)
    assert out.strip() == "ЯДРО"


def test_порядок_источников_сохраняется(blocks):
    out = assemble({"источники": _и("чаты", "транскрипты"), "площадки": []}, blocks)
    assert out.index("ЧАТЫ") < out.index("ТРАНСКРИПТЫ")


def test_неизвестный_источник_падает_с_понятным_текстом(blocks):
    with pytest.raises(ValueError, match="нет блока для источника «выдумка»"):
        assemble({"источники": _и("выдумка"), "площадки": []}, blocks)


def test_нет_ядра_падает(tmp_path):
    with pytest.raises(FileNotFoundError, match="core.md"):
        assemble({"источники": [], "площадки": []}, tmp_path)
