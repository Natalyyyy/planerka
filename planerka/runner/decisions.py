"""Разбор решений человека из файла недели.

Маркеры: [x] беру, [?] подумать, [-] нет, [ ] не решено.
"""
import re

СТРОКА = re.compile(r"^[-*]\s*\[(.)\]\s*(.*)$")
СТРОКА_ПРОВЕРКА = re.compile(r"^[-*]\s*\[(.)\]")
ЗАГОЛОВОК_БАНКА = re.compile(r"^##\s+банк\s+тем\s*$", re.IGNORECASE)
ЗАГОЛОВОК_РАЗДЕЛА = re.compile(r"^##\s+")
СОСТОЯНИЕ = {"x": "беру", "?": "подумать", "-": "нет", " ": "не_решено"}


def parse_decisions(text: str) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {
        "беру": [],
        "подумать": [],
        "нет": [],
        "не_решено": [],
        "пропущено": [],
    }

    lines = text.splitlines()

    in_code_block = False
    in_bank_section = False

    for line in lines:
        # Переключаем состояние блока кода
        if line.strip().startswith("```"):
            in_code_block = not in_code_block
            continue

        # Пропускаем строки внутри блока кода
        if in_code_block:
            # Если это выглядит как решение, но в блоке кода, класть в пропущено
            if СТРОКА_ПРОВЕРКА.match(line.strip()):
                out["пропущено"].append(line.rstrip())
            continue

        # Проверяем, это ли начало раздела "Банк тем"
        if ЗАГОЛОВОК_БАНКА.match(line.strip()):
            in_bank_section = True
            continue

        # Проверяем, это ли начало другого раздела (##)
        if ЗАГОЛОВОК_РАЗДЕЛА.match(line.strip()):
            in_bank_section = False
            continue

        # Обработка в зависимости от раздела
        if in_bank_section:
            # Разбираем только строки без отступа в начале
            if line and line[0] in " \t":
                # Вложенная строка — проверяем, есть ли в ней галочка
                if СТРОКА_ПРОВЕРКА.match(line.strip()):
                    out["пропущено"].append(line.rstrip())
                continue

            # Пытаемся распарсить строку
            м = СТРОКА.match(line.strip())
            if not м:
                continue

            маркер = м[1].lower()
            состояние = СОСТОЯНИЕ.get(маркер)

            if состояние is None:
                # Неизвестный маркер
                out["пропущено"].append(line.rstrip())
                continue

            тема_сырая = м[2].strip()

            # Режем по литералу "· откуда:", а не по любому "·"
            if "· откуда:" in тема_сырая:
                тема = тема_сырая.split("· откуда:")[0].strip()
            else:
                тема = тема_сырая

            # Пустую тему не кладём в список, кладём в пропущено
            if not тема:
                out["пропущено"].append(line.rstrip())
                continue

            out[состояние].append(тема)
        else:
            # Вне раздела Банк тем — отслеживаем галочки
            if СТРОКА_ПРОВЕРКА.match(line.strip()):
                out["пропущено"].append(line.rstrip())

    return out
