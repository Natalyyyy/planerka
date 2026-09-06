"""Сборка личного промпта из блоков.

Неподключённый источник в итоговый промпт не попадает вообще — это
принципиально: мёртвая строка про источник, которого у человека нет,
заставляет модель искать несуществующее.
"""
from pathlib import Path


def _read(path: Path, вид: str, имя: str) -> str:
    if not path.exists():
        raise ValueError(f"нет блока для {вид} «{имя}»: ждали {path}")
    return path.read_text(encoding="utf-8").strip()


def assemble(config: dict, blocks_dir: Path, ядро: str = "core.md",
             с_источниками: bool = True) -> str:
    """Личный промпт из блоков.

    `с_источниками=False` — для такта Б: он работает с уже решёнными темами,
    а не с материалом источников. Блок источника написан под роль такта А и
    прямо говорит, чего в такте А делать не надо («по дням не раскладывают»);
    приехав в такт Б, он запрещает ровно то, ради чего такт Б и запускают.
    """
    core = blocks_dir / ядро
    if not core.exists():
        raise FileNotFoundError(f"нет ядра промпта: ждали {core}")

    куски = [core.read_text(encoding="utf-8").strip()]
    for источник in (config.get("источники", []) if с_источниками else []):
        имя = источник["имя"]
        куски.append(_read(blocks_dir / "sources" / f"{имя}.md", "источника", имя))
    for имя in config.get("площадки", []):
        куски.append(_read(blocks_dir / "platforms" / f"{имя}.md", "площадки", имя))
    return "\n\n".join(куски)
