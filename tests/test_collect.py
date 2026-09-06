from datetime import date
from pathlib import Path
from planerka.runner.collect import collect


def _конфиг(имя="транскрипты", путь="встречи", окно=45):
    return {"источники": [{"имя": имя, "путь": путь, "окно_дней": окно}]}


def test_берёт_файлы_из_папки(tmp_path):
    (tmp_path / "встречи").mkdir()
    (tmp_path / "встречи" / "созвон – 2026-09-01.md").write_text("текст встречи", encoding="utf-8")
    out = collect(_конфиг(), tmp_path, date(2026, 9, 5))
    assert "текст встречи" in out["транскрипты"]


def test_файл_старше_окна_не_берётся(tmp_path):
    (tmp_path / "встречи").mkdir()
    (tmp_path / "встречи" / "старое – 2026-01-01.md").write_text("древность", encoding="utf-8")
    out = collect(_конфиг(окно=45), tmp_path, date(2026, 9, 5))
    assert "древность" not in out["транскрипты"]


def test_окно_none_берёт_всё(tmp_path):
    (tmp_path / "встречи").mkdir()
    (tmp_path / "встречи" / "старое – 2026-01-01.md").write_text("древность", encoding="utf-8")
    out = collect(_конфиг(окно=None), tmp_path, date(2026, 9, 5))
    assert "древность" in out["транскрипты"]


def test_папки_нет_пустая_строка_а_не_падение(tmp_path):
    out = collect(_конфиг(), tmp_path, date(2026, 9, 5))
    assert out["транскрипты"] == ""


def test_пустая_папка_пустая_строка(tmp_path):
    (tmp_path / "встречи").mkdir()
    out = collect(_конфиг(), tmp_path, date(2026, 9, 5))
    assert out["транскрипты"] == ""


def test_файл_без_даты_в_имени_берётся_всегда(tmp_path):
    (tmp_path / "встречи").mkdir()
    (tmp_path / "встречи" / "бэклог.md").write_text("живой архив", encoding="utf-8")
    out = collect(_конфиг(), tmp_path, date(2026, 9, 5))
    assert "живой архив" in out["транскрипты"]


def test_нечитаемый_файл_пропускается_а_прогон_живёт(tmp_path):
    (tmp_path / "встречи").mkdir()
    битый = tmp_path / "встречи" / "битый.md"
    битый.write_bytes(b"\xff\xfe\x00\x80\x81\x82")
    (tmp_path / "встречи" / "живой.md").write_text("живой текст", encoding="utf-8")
    out = collect(_конфиг(), tmp_path, date(2026, 9, 5))
    assert "живой текст" in out["транскрипты"]
