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

    # Первый проход: найти закрытые блоки кода
    closed_code_lines = set()
    in_code_block = False
    block_start = None

    for i, line in enumerate(lines):
        if line.strip().startswith("```"):
            if not in_code_block:
                block_start = i
                in_code_block = True
            else:
                # Блок закрывается — отметить все строки в нём
                for j in range(block_start, i + 1):
                    closed_code_lines.add(j)
                in_code_block = False
                block_start = None

    # Второй проход: основной разбор
    in_code_block = False
    in_bank_section = False

    for i, line in enumerate(lines):
        # Переключаем состояние блока кода
        if line.strip().startswith("```"):
            in_code_block = not in_code_block
            continue

        # Пропускаем строки внутри закрытого блока кода полностью
        if i in closed_code_lines:
            continue

        # Если вижу заголовок раздела, закрываю открытый блок
        if ЗАГОЛОВОК_РАЗДЕЛА.match(line.strip()):
            in_code_block = False
            # Проверяем, это ли начало раздела "Банк тем"
            if ЗАГОЛОВОК_БАНКА.match(line.strip()):
                in_bank_section = True
            else:
                in_bank_section = False
            continue

        # Если в незакрытом блоке кода и выглядит как решение — в пропущено
        if in_code_block:
            if СТРОКА_ПРОВЕРКА.match(line.strip()):
                out["пропущено"].append(line.rstrip())
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
