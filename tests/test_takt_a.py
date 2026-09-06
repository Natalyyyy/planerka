import pytest
from datetime import date
from planerka.runner.takt_a import takt_a


@pytest.fixture
def мир(tmp_path):
    блоки = tmp_path / "blocks"
    (блоки / "sources").mkdir(parents=True)
    (блоки / "platforms").mkdir()
    (блоки / "core.md").write_text("ЯДРО", encoding="utf-8")
    (блоки / "sources" / "заметки.md").write_text("ЗАМЕТКИ", encoding="utf-8")
    заметки = tmp_path / "notes"
    (заметки / "черновики").mkdir(parents=True)
    (заметки / "черновики" / "мысль.md").write_text("живая мысль", encoding="utf-8")
    конфиг = {
        "источники": [{"имя": "заметки", "путь": "черновики", "окно_дней": None}],
        "площадки": [],
        "модель": "claude-sonnet-5",
    }
    return конфиг, заметки, блоки


def test_пишет_файл_недели_и_возвращает_путь(мир):
    конфиг, заметки, блоки = мир
    путь = takt_a(конфиг, заметки, блоки, date(2026, 9, 5), зов=lambda *a, **k: "## Банк тем\n\n- [ ] Тема")
    assert путь.exists()
    assert путь.name == "неделя – 2026-08-31.md"
    assert "- [ ] Тема" in путь.read_text(encoding="utf-8")


def test_в_промпт_уехали_и_блоки_и_собранный_контекст(мир):
    конфиг, заметки, блоки = мир
    видел = {}

    def зов(prompt, model, **k):
        видел["промпт"] = prompt
        видел["модель"] = model
        return "## Банк тем\n\n- [ ] Тема"

    takt_a(конфиг, заметки, блоки, date(2026, 9, 5), зов=зов)
    assert "ЯДРО" in видел["промпт"]
    assert "ЗАМЕТКИ" in видел["промпт"]
    assert "живая мысль" in видел["промпт"]


def test_модель_передаётся_явно(мир):
    конфиг, заметки, блоки = мир
    видел = {}

    def зов(prompt, model, **k):
        видел["модель"] = model
        return "## Банк тем\n\n- [ ] Тема"

    takt_a(конфиг, заметки, блоки, date(2026, 9, 5), зов=зов)
    assert видел["модель"] == "claude-sonnet-5"


def test_пустой_ответ_модели_не_затирает_прошлый_файл(мир):
    конфиг, заметки, блоки = мир
    первый = takt_a(конфиг, заметки, блоки, date(2026, 9, 5), зов=lambda *a, **k: "## Банк тем\n\n- [x] Старое")
    with pytest.raises(RuntimeError, match="пустой ответ"):
        takt_a(конфиг, заметки, блоки, date(2026, 9, 5), зов=lambda *a, **k: "   ")
    assert "Старое" in первый.read_text(encoding="utf-8")


def test_падение_зова_не_оставляет_обрубок(мир):
    конфиг, заметки, блоки = мир
    def падает(*a, **k):
        raise TimeoutError("модель молчит")
    with pytest.raises(TimeoutError):
        takt_a(конфиг, заметки, блоки, date(2026, 9, 5), зов=падает)
    assert not (заметки / "недели").exists() or list((заметки / "недели").glob("*.md")) == []


def test_ни_одного_источника_прогон_всё_равно_идёт(мир):
    конфиг, заметки, блоки = мир
    конфиг = {**конфиг, "источники": []}
    путь = takt_a(конфиг, заметки, блоки, date(2026, 9, 5), зов=lambda *a, **k: "## Банк тем\n\n- [ ] Тема")
    assert путь.exists()
