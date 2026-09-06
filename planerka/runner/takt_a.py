"""Такт А: аналитика недели и банк тем без расстановки по дням."""
import os
from datetime import date, timedelta
from pathlib import Path

from .assemble import assemble
from .collect import collect
from .llm import run_claude
from .person import личный_контекст


def начало_недели(день: date) -> date:
    return день - timedelta(days=день.weekday())


def takt_a(config: dict, notes_root: Path, blocks_dir: Path, today: date, зов=run_claude) -> Path:
    промпт = assemble(config, blocks_dir)
    личное = личный_контекст(config, notes_root)
    if личное:
        промпт += "\n\n" + личное
    контекст = collect(config, notes_root, today)
    for имя, текст in контекст.items():
        промпт += f"\n\n## Источник: {имя}\n{текст}" if текст else f"\n\n## Источник: {имя}\n(пусто)"

    ответ = зов(промпт, model=config["модель"])
    if not ответ or not ответ.strip():
        raise RuntimeError("пустой ответ модели — файл недели не тронут")

    каталог = notes_root / "недели"
    каталог.mkdir(parents=True, exist_ok=True)
    путь = каталог / f"неделя – {начало_недели(today)}.md"
    временный = путь.with_suffix(путь.suffix + ".tmp")
    временный.write_text(ответ.strip() + "\n", encoding="utf-8")
    os.replace(временный, путь)
    return путь
