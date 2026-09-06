"""README обещал команды, которых в плагине нет.

Он звал `/планёрка-настройка`, `/планёрка темы`, `/планёрка план`, а каталога
`commands/` в плагине не было вообще: скиллы зовутся `planerka-setup` и
`planerka`. Первое же действие первого пользователя после установки не
срабатывало.
"""
import re
from pathlib import Path

КОРЕНЬ = Path(__file__).resolve().parents[1]
README = (КОРЕНЬ / "README.md").read_text(encoding="utf-8")

# Команда в тексте: в обратных кавычках (`/planerka:имя`) или строкой в блоке
# кода — блок установки написан именно так, и мимо сторожа он проходить не
# должен.
В_КАВЫЧКАХ = re.compile(r"`/([^`\s]+)")
СТРОКОЙ = re.compile(r"^/(\S+)", re.MULTILINE)


def команды_из_readme() -> list[str]:
    return В_КАВЫЧКАХ.findall(README) + СТРОКОЙ.findall(README)


def имена_скиллов() -> set[str]:
    имена = {п.name for п in (КОРЕНЬ / "planerka" / "skills").iterdir() if п.is_dir()}
    assert имена, "в плагине нет ни одного скилла"
    return имена


def test_каждая_команда_из_readme_существует():
    встроенные = {"plugin"}  # /plugin marketplace add, /plugin install
    скиллы = имена_скиллов()
    выдуманные = []
    for слово in команды_из_readme():
        if слово in встроенные:
            continue
        плагин, _, имя = слово.partition(":")
        if плагин != "planerka" or имя not in скиллы:
            выдуманные.append(слово)
    assert not выдуманные, f"README зовёт то, чего в плагине нет: {выдуманные}"


def test_установка_идёт_из_репозитория_а_не_из_папки_автора():
    assert "Natalyyyy/planerka" in README
    assert "~/Projects" not in README
