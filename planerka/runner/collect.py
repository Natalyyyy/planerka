"""Сбор контекста из подключённых источников.

Источника нет — пустая строка, не падение. Планёрка обязана отработать у
человека, который подключил два источника из девяти.
"""
import re
from datetime import date, timedelta
from pathlib import Path

ДАТА = re.compile(r"(\d{4})-(\d{2})-(\d{2})")


def _дата_из_имени(имя: str) -> date | None:
    м = ДАТА.search(имя)
    if not м:
        return None
    try:
        return date(int(м[1]), int(м[2]), int(м[3]))
    except ValueError:
        return None


def collect(config: dict, notes_root: Path, today: date) -> dict[str, str]:
    собрано: dict[str, str] = {}
    for источник in config.get("источники", []):
        папка = notes_root / источник["путь"]
        if not папка.is_dir():
            собрано[источник["имя"]] = ""
            continue

        окно = источник.get("окно_дней")
        граница = today - timedelta(days=окно) if окно else None
        куски = []
        for файл in sorted(папка.rglob("*.md")):
            д = _дата_из_имени(файл.name)
            if граница and д and д < граница:
                continue
            try:
                куски.append(f"### {файл.name}\n{файл.read_text(encoding='utf-8')}")
            except (UnicodeDecodeError, OSError):
                continue
        собрано[источник["имя"]] = "\n\n".join(куски)
    return собрано
