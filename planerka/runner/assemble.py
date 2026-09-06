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


def assemble(config: dict, blocks_dir: Path, ядро: str = "core.md") -> str:
    core = blocks_dir / ядро
    if not core.exists():
        raise FileNotFoundError(f"нет ядра промпта: ждали {core}")

    куски = [core.read_text(encoding="utf-8").strip()]
    for источник in config.get("источники", []):
        имя = источник["имя"]
        куски.append(_read(blocks_dir / "sources" / f"{имя}.md", "источника", имя))
    for имя in config.get("площадки", []):
        куски.append(_read(blocks_dir / "platforms" / f"{имя}.md", "площадки", имя))
    return "\n\n".join(куски)
