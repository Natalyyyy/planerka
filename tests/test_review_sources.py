from datetime import date
from pathlib import Path
import warnings

import pytest

import planerka.runner.collect as collect_module
import planerka.runner.takt_b as takt_b_module
from planerka.runner.collect import collect
from planerka.runner.takt_a import takt_a
from planerka.runner.takt_b import takt_b


def _blocks(tmp_path):
    blocks = tmp_path / "blocks"
    (blocks / "sources").mkdir(parents=True)
    (blocks / "platforms").mkdir()
    (blocks / "core.md").write_text("core", encoding="utf-8")
    (blocks / "core-план.md").write_text("core plan", encoding="utf-8")
    return blocks


def test_takt_b_archives_rejected_topics_even_when_none_are_taken(tmp_path):
    blocks = _blocks(tmp_path)
    notes = tmp_path / "notes"
    weeks = notes / "недели"
    weeks.mkdir(parents=True)
    week = weeks / "неделя – 2026-08-31.md"
    week.write_text("## Банк тем\n\n- [-] Отклонённая тема\n", encoding="utf-8")
    config = {"источники": [], "площадки": [], "модель": "claude-sonnet-5"}

    with pytest.raises(RuntimeError, match="ни одной взятой темы"):
        takt_b(config, notes, blocks, date(2026, 9, 5), зов=lambda *a, **k: "unused")

    archive = notes / "отклонённые.md"
    assert "Отклонённая тема" in archive.read_text(encoding="utf-8")


def test_takt_b_archive_is_idempotent_across_two_runs(tmp_path):
    blocks = _blocks(tmp_path)
    notes = tmp_path / "notes"
    weeks = notes / "недели"
    weeks.mkdir(parents=True)
    (weeks / "неделя – 2026-08-31.md").write_text(
        "## Банк тем\n\n- [x] Взятая\n- [-] Отклонённая · откуда: тест\n",
        encoding="utf-8",
    )
    config = {"источники": [], "площадки": [], "модель": "claude-sonnet-5"}
    зов = lambda *a, **k: "## Неделя по дням\n\nПн — Взятая"

    takt_b(config, notes, blocks, date(2026, 9, 5), зов=зов)
    takt_b(config, notes, blocks, date(2026, 9, 5), зов=зов)

    lines = (notes / "отклонённые.md").read_text(encoding="utf-8").splitlines()
    assert sum("Отклонённая" in line for line in lines) == 1


def test_takt_b_with_no_rejected_topics_does_not_create_archive(tmp_path):
    blocks = _blocks(tmp_path)
    notes = tmp_path / "notes"
    weeks = notes / "недели"
    weeks.mkdir(parents=True)
    (weeks / "неделя – 2026-08-31.md").write_text(
        "## Банк тем\n\n- [ ] Не решена\n", encoding="utf-8"
    )
    config = {"источники": [], "площадки": [], "модель": "claude-sonnet-5"}

    with pytest.raises(RuntimeError, match="ни одной взятой темы"):
        takt_b(config, notes, blocks, date(2026, 9, 5), зов=lambda *a, **k: "unused")

    assert not (notes / "отклонённые.md").exists()


def test_takt_b_archive_write_error_keeps_week_file_unchanged(tmp_path, monkeypatch):
    blocks = _blocks(tmp_path)
    notes = tmp_path / "notes"
    weeks = notes / "недели"
    weeks.mkdir(parents=True)
    week = weeks / "неделя – 2026-08-31.md"
    original = "## Банк тем\n\n- [-] Отклонённая\n"
    week.write_text(original, encoding="utf-8")
    config = {"источники": [], "площадки": [], "модель": "claude-sonnet-5"}

    def fail_archive(path, text):
        raise OSError("диск недоступен")

    monkeypatch.setattr(takt_b_module, "записать_атомарно", fail_archive)
    with pytest.raises(OSError, match="диск недоступен"):
        takt_b(config, notes, blocks, date(2026, 9, 5), зов=lambda *a, **k: "unused")

    assert week.read_text(encoding="utf-8") == original


def test_collect_warns_for_missing_and_unreadable_sources(tmp_path):
    (tmp_path / "битый.md").write_bytes(b"\xff\xfe\x80")
    config = {"источники": [
        {"имя": "пропавший", "путь": "нет.md", "окно_дней": None},
        {"имя": "битый источник", "путь": "битый.md", "окно_дней": None},
    ]}

    with pytest.warns(UserWarning) as captured:
        result = collect(config, tmp_path, date(2026, 9, 5))

    assert result == {"пропавший": "", "битый источник": ""}
    warnings = " ".join(str(item.message) for item in captured)
    assert "пропавший" in warnings and "битый источник" in warnings


def test_collect_empty_directory_and_file_do_not_warn(tmp_path):
    (tmp_path / "пустая-папка").mkdir()
    (tmp_path / "пустой.md").write_text("", encoding="utf-8")
    config = {"источники": [
        {"имя": "папка", "путь": "пустая-папка", "окно_дней": None},
        {"имя": "файл", "путь": "пустой.md", "окно_дней": None},
    ]}

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        result = collect(config, tmp_path, date(2026, 9, 5))

    assert result == {"папка": "", "файл": "### пустой.md\n"}
    assert caught == []


def test_collect_warns_for_broken_nested_file_and_keeps_valid_one(tmp_path):
    folder = tmp_path / "встречи"
    (folder / "вложенная").mkdir(parents=True)
    (folder / "вложенная" / "битый.md").write_bytes(b"\xff\xfe\x80")
    (folder / "вложенная" / "живой.md").write_text("доступная встреча", encoding="utf-8")
    config = {"источники": [{"имя": "встречи", "путь": "встречи", "окно_дней": None}]}

    with pytest.warns(UserWarning, match="битый.md"):
        result = collect(config, tmp_path, date(2026, 9, 5))

    assert "доступная встреча" in result["встречи"]


def test_collect_warns_when_directory_scan_fails(tmp_path, monkeypatch):
    folder = tmp_path / "недоступная-папка"
    folder.mkdir()
    real_scandir = collect_module.os.scandir

    def fail_scan(path):
        if Path(path) == folder:
            raise PermissionError("нет доступа к каталогу")
        return real_scandir(path)

    monkeypatch.setattr(collect_module.os, "scandir", fail_scan)
    config = {"источники": [{"имя": "архив", "путь": folder.name, "окно_дней": None}]}

    with pytest.warns(UserWarning, match="не удалось прочесть каталог"):
        result = collect(config, tmp_path, date(2026, 9, 5))

    assert result == {"архив": ""}


def test_collect_warns_when_nested_file_read_raises_permission_error(tmp_path, monkeypatch):
    folder = tmp_path / "встречи"
    folder.mkdir()
    denied = folder / "закрытая.md"
    denied.write_text("секрет", encoding="utf-8")
    real_read_text = Path.read_text

    def fail_read(path, *args, **kwargs):
        if path == denied:
            raise PermissionError("нет доступа к файлу")
        return real_read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", fail_read)
    config = {"источники": [{"имя": "встречи", "путь": folder.name, "окно_дней": None}]}

    with pytest.warns(UserWarning, match="закрытая.md"):
        result = collect(config, tmp_path, date(2026, 9, 5))

    assert result == {"встречи": ""}


def test_takt_a_rejects_nonempty_model_answer_without_bank(tmp_path):
    blocks = _blocks(tmp_path)
    notes = tmp_path / "notes"
    notes.mkdir()
    config = {"источники": [], "площадки": [], "модель": "claude-sonnet-5"}

    with pytest.raises(RuntimeError, match="банке тем"):
        takt_a(config, notes, blocks, date(2026, 9, 5), зов=lambda *a, **k: "Я не смог подготовить темы.")

    assert not (notes / "недели" / "неделя – 2026-08-31.md").exists()


@pytest.mark.parametrize("answer", [
    "## Банк тем\n\nЭто не строка темы.",
    "## Банк тем\n\n- [q] неизвестный маркер",
    "## Банк тем\n\n```md\n- [ ] тема внутри кода\n```",
])
def test_takt_a_rejects_malformed_or_code_only_bank_without_overwriting(tmp_path, answer):
    blocks = _blocks(tmp_path)
    notes = tmp_path / "notes"
    weeks = notes / "недели"
    weeks.mkdir(parents=True)
    week = weeks / "неделя – 2026-08-31.md"
    original = "## Банк тем\n\n- [x] Существующая тема\n"
    week.write_text(original, encoding="utf-8")
    config = {"источники": [], "площадки": [], "модель": "claude-sonnet-5"}
    called = []

    with pytest.raises(RuntimeError, match="разбираемых тем"):
        takt_a(config, notes, blocks, date(2026, 9, 5), зов=lambda *a, **k: called.append(True) or answer)

    assert called == [True]
    assert week.read_text(encoding="utf-8") == original


def test_takt_a_model_error_keeps_existing_week_unchanged(tmp_path):
    blocks = _blocks(tmp_path)
    notes = tmp_path / "notes"
    weeks = notes / "недели"
    weeks.mkdir(parents=True)
    week = weeks / "неделя – 2026-08-31.md"
    original = "## Банк тем\n\n- [x] Существующая тема\n"
    week.write_text(original, encoding="utf-8")
    config = {"источники": [], "площадки": [], "модель": "claude-sonnet-5"}

    def model_error(*args, **kwargs):
        raise TimeoutError("модель не отвечает")

    with pytest.raises(TimeoutError, match="модель не отвечает"):
        takt_a(config, notes, blocks, date(2026, 9, 5), зов=model_error)

    assert week.read_text(encoding="utf-8") == original
