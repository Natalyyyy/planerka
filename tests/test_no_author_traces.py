import re
from pathlib import Path
import pytest

КОРЕНЬ = Path(__file__).resolve().parents[1]
СЛЕДЫ = [
    "Наташ", "Дудин", "natashhhh", "nataliadudina", "ObsidianVault",
    "Начальник тоже человек", "Марс", "marsing", "Имба", "ai-native",
    "rasp@", "/home/rasp", "TGStat", "Практикум",
]
ПРОПУСК_ПАПОК = {".git", "__pycache__", ".venv", ".pytest_cache"}
ПРОПУСК_ФАЙЛОВ = {"tests/test_no_author_traces.py"}

ЗАКОННОЕ = {
    (".claude-plugin/marketplace.json", "Наташ"),
    (".claude-plugin/marketplace.json", "Дудин"),
    ("LICENSE", "Наташ"),
    ("LICENSE", "Дудин"),
    ("README.md", "Наташ"),
    ("README.md", "Дудин"),
    # Авторский блок README: название канала и ссылка на него законны там же,
    # где стоит имя автора. Больше нигде в репозитории их быть не должно.
    ("README.md", "Начальник тоже человек"),
    ("README.md", "natashhhh"),
}


def файлы():
    for п in КОРЕНЬ.rglob("*"):
        if not п.is_file() or any(ч in ПРОПУСК_ПАПОК for ч in п.parts):
            continue
        отн = str(п.relative_to(КОРЕНЬ))
        if отн in ПРОПУСК_ФАЙЛОВ:
            continue
        if п.suffix not in {".md", ".py", ".json", ".sh", ""}:
            continue
        yield п


@pytest.mark.parametrize("след", СЛЕДЫ)
def test_следа_автора_нет_нигде(след):
    попались = []
    for п in файлы():
        отн = str(п.relative_to(КОРЕНЬ))
        if (отн, след) in ЗАКОННОЕ:
            continue
        try:
            текст = п.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if re.search(re.escape(след), текст, re.IGNORECASE):
            попались.append(отн)
    assert not попались, f"след «{след}» найден в: {попались}"
