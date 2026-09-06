"""Сбор контекста из подключённых источников.

Источника нет — пустая строка, не падение. Планёрка обязана отработать у
человека, который подключил два источника из девяти.
"""
import re
from datetime import date, timedelta
from pathlib import Path

ДАТА = re.compile(r"(\d{4})-(\d{2})-(\d{2})")


def _дата_из_имени(имя: str) -> date | None:
    совпадения = list(ДАТА.finditer(имя))
    if not совпадения:
        return None
    м = совпадения[-1]  # берём последнее совпадение
    try:
        return date(int(м[1]), int(м[2]), int(м[3]))
    except ValueError:
        return None


def _кусок(файл: Path, граница: date | None) -> str | None:
    """Один файл в виде куска промпта. None — файл не подошёл или не прочёлся."""
    д = _дата_из_имени(файл.name)
    if граница and д and д < граница:
        return None
    try:
        return f"### {файл.name}\n{файл.read_text(encoding='utf-8')}"
    except (UnicodeDecodeError, OSError):
        return None


def collect(config: dict, notes_root: Path, today: date) -> dict[str, str]:
    собрано: dict[str, str] = {}
    for источник in config.get("источники", []):
        путь = notes_root / источник["путь"]
        окно = источник.get("окно_дней")
        граница = today - timedelta(days=окно) if окно else None

        # Источник — это либо папка, либо один файл. Журнал сделанного живёт
        # одним файлом в папке заметок, и требование «только директория»
        # молча отдавало по нему пустоту: тихая пустота хуже ошибки, потому
        # что выглядит как «на этой неделе ничего не было».
        if путь.is_file():
            кусок = _кусок(путь, граница)
            собрано[источник["имя"]] = кусок or ""
            continue

        if not путь.is_dir():
            собрано[источник["имя"]] = ""
            continue

        куски = [к for к in (_кусок(ф, граница) for ф in sorted(путь.rglob("*.md"))) if к]
        собрано[источник["имя"]] = "\n\n".join(куски)
    return собрано
