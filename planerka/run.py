#!/usr/bin/env python3
"""Точка входа планёрки: один такт за запуск.

    python3 run.py темы  --папка /путь/к/заметкам
    python3 run.py план

Файл лежит в корне плагина, и путь к нему скилл подставляет сам —
`${CLAUDE_PLUGIN_ROOT}/run.py`. Пакет здесь не импортируется по имени:
после установки каталог плагина лежит в кэше Claude Code, родителя пакета на
`sys.path` нет, и `import planerka` даёт ModuleNotFoundError. Поэтому в путь
кладётся собственный каталог, а модули берутся из него.

Где лежит папка заметок, знает либо аргумент `--папка`, либо указатель
`~/.planerka/папка.txt`, который пишется при первом запуске с аргументом.
Круг «конфиг лежит в папке заметок, а путь к папке заметок лежит в конфиге»
разрывается именно тут: угадывать путь нечем и незачем.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

# Проверка версии стоит до импорта раннера намеренно. Код планёрки написан на
# синтаксисе 3.10 (`date | None`), а `python3` на маке из коробки — 3.9: без
# этой проверки человек получает TypeError из середины чужого файла и не
# понимает ни при чём тут он, ни что делать дальше.
if sys.version_info < (3, 10):
    сейчас = ".".join(str(ч) for ч in sys.version_info[:3])
    print(f"Планёрке нужен Python 3.10 или новее, а этот — {сейчас} ({sys.executable}). "
          "Поставьте свежий Python и запустите команду им.", file=sys.stderr)
    raise SystemExit(1)

КОРЕНЬ = Path(__file__).resolve().parent
sys.path.insert(0, str(КОРЕНЬ))

from runner.takt_a import takt_a  # noqa: E402
from runner.takt_b import takt_b  # noqa: E402

УКАЗАТЕЛЬ = Path.home() / ".planerka" / "папка.txt"
ТАКТЫ = {"темы": takt_a, "план": takt_b}


def _умереть(сообщение: str) -> None:
    print(сообщение, file=sys.stderr)
    raise SystemExit(1)


def _прочесть_указатель() -> Path | None:
    try:
        строка = УКАЗАТЕЛЬ.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return Path(строка).expanduser() if строка else None


def _записать_указатель(папка: Path) -> None:
    try:
        УКАЗАТЕЛЬ.parent.mkdir(parents=True, exist_ok=True)
        УКАЗАТЕЛЬ.write_text(str(папка) + "\n", encoding="utf-8")
    except OSError:
        pass  # не смогли запомнить — не повод ронять прогон


def main(аргументы: list[str] | None = None) -> None:
    парсер = argparse.ArgumentParser(
        prog="run.py", description="Планёрка: такт «темы» или такт «план»")
    парсер.add_argument("такт", choices=sorted(ТАКТЫ),
                        help="темы — собрать банк тем, план — собрать план недели")
    парсер.add_argument("--папка", help="папка заметок, где лежит конфиг.json")
    разобрано = парсер.parse_args(аргументы)

    названа = bool(разобрано.папка)
    папка = Path(разобрано.папка).expanduser() if названа else _прочесть_указатель()
    if папка is None:
        _умереть(
            "Не знаю, где папка заметок: указателя "
            f"{УКАЗАТЕЛЬ} нет. Запустите ещё раз и передайте путь: "
            "--папка /путь/к/заметкам")

    конфиг_файл = папка / "конфиг.json"
    if not конфиг_файл.is_file():
        _умереть(f"В папке {папка} нет конфиг.json — планёрка там ещё не настроена")

    try:
        конфиг = json.loads(конфиг_файл.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as ошибка:
        _умереть(f"Не читается {конфиг_файл}: {ошибка}")

    if not конфиг.get("модель"):
        _умереть(f"В {конфиг_файл} нет поля «модель» — допишите его или перенастройте планёрку")

    notes_root = Path(конфиг.get("папка_заметок") or папка).expanduser()
    if not notes_root.is_dir():
        _умереть(f"Папка заметок из конфига не найдена: {notes_root}")

    if названа:
        _записать_указатель(папка)

    путь = ТАКТЫ[разобрано.такт](конфиг, notes_root, КОРЕНЬ / "blocks", date.today())
    print(f"Готово. Файл недели: {путь}")


if __name__ == "__main__":
    main()
