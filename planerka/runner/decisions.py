"""Разбор решений человека из файла недели.

Маркеры: [x] беру, [?] подумать, [-] нет, [ ] не решено.
"""
import re

СТРОКА = re.compile(r"^[-*]\s*\[(.)\]\s*(.*)$")
СТРОКА_ПРОВЕРКА = re.compile(r"^[-*]\s*\[(.)\]")
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

    # Найти границы раздела "## Банк тем"
    bank_start = None
    bank_end = len(lines)

    for i, line in enumerate(lines):
        if line.strip() == "## Банк тем":
            bank_start = i + 1
        elif bank_start is not None and line.startswith("##"):
            bank_end = i
            break

    # Если раздела "Банк тем" нет, отслеживаем все строки с галочками
    if bank_start is None:
        in_code_block = False
        for line in lines:
            if line.strip().startswith("```"):
                in_code_block = not in_code_block
                continue
            if in_code_block:
                continue
            if СТРОКА_ПРОВЕРКА.match(line.strip()):
                out["пропущено"].append(line.rstrip())
        return out

    # Обработать строки в пределах раздела, пропуская блоки кода
    in_code_block = False
    for i in range(bank_start, bank_end):
        line = lines[i]

        # Отслеживаем блоки кода
        if line.strip().startswith("```"):
            in_code_block = not in_code_block
            continue

        # Пропускаем содержимое блоков кода
        if in_code_block:
            continue

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

    # Отслеживаем строки с галочками ДО раздела Банк тем
    in_code_block = False
    for i in range(0, bank_start - 1):
        line = lines[i]

        if line.strip().startswith("```"):
            in_code_block = not in_code_block
            continue

        if in_code_block:
            continue

        if СТРОКА_ПРОВЕРКА.match(line.strip()):
            out["пропущено"].append(line.rstrip())

    # Отслеживаем строки с галочками ПОСЛЕ раздела Банк тем
    in_code_block = False
    for i in range(bank_end, len(lines)):
        line = lines[i]

        if line.strip().startswith("```"):
            in_code_block = not in_code_block
            continue

        if in_code_block:
            continue

        if СТРОКА_ПРОВЕРКА.match(line.strip()):
            out["пропущено"].append(line.rstrip())

    return out
