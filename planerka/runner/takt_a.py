"""Такт А: аналитика недели и банк тем без расстановки по дням."""
import os
from datetime import date, timedelta
from pathlib import Path

from .assemble import assemble
from .collect import collect
from .llm import run_claude
from .person import личный_контекст
from .weeks import найти_файл_недели, неразобранное


def начало_недели(день: date) -> date:
    return день - timedelta(days=день.weekday())


def _сказать_про_прошлую_неделю(notes_root: Path, новый: Path) -> None:
    """Предупредить, что в прошлом файле недели остались нерешённые темы.

    Такт А пишет новый файл с нуля и прошлую неделю не переносит. Пока он об
    этом молчал, неделя размеченных решений просто оставалась мёртвой, и
    человек узнавал об этом только сам, случайно, открыв старый файл.
    """
    прошлый = найти_файл_недели(notes_root)
    if прошлый is None or прошлый == новый:
        return
    осталось = неразобранное(прошлый)
    if not осталось:
        return
    сколько = ", ".join(
        f"{'не отмечено' if вид == 'не_решено' else 'отложено'}: {len(темы)}"
        for вид, темы in осталось.items()
    )
    примеры = [т for темы in осталось.values() for т in темы][:3]
    print(
        f"Внимание: в прошлом файле «{прошлый.name}» остались нерешённые темы "
        f"({сколько}). Они никуда не переносятся — решите их там или "
        f"перенесите в новый файл руками. Например: "
        + "; ".join(примеры)
    )


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
    _сказать_про_прошлую_неделю(notes_root, путь)
    os.replace(временный, путь)
    return путь
