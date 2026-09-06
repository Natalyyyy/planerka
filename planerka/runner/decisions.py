"""Разбор решений человека из файла недели.

Маркеры: [x] беру, [?] подумать, [-] нет, [ ] не решено.
"""
import re

СТРОКА = re.compile(r"^\s*-\s*\[(.)\]\s*(.+?)\s*$")
СОСТОЯНИЕ = {"x": "беру", "?": "подумать", "-": "нет", " ": "не_решено"}


def parse_decisions(text: str) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {"беру": [], "подумать": [], "нет": [], "не_решено": []}
    for строка in text.splitlines():
        м = СТРОКА.match(строка)
        if not м:
            continue
        состояние = СОСТОЯНИЕ.get(м[1].lower())
        if состояние is None:
            continue
        тема = м[2].split("·")[0].strip()
        out[состояние].append(тема)
    return out
