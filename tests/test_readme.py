"""README обещал команды, которых в плагине нет.

Он звал `/планёрка-настройка`, `/планёрка темы`, `/планёрка план`, а каталога
`commands/` в плагине не было вообще: скиллы зовутся `planerka-setup` и
`planerka`. Первое же действие первого пользователя после установки не
срабатывало.

Задача 6 части 2 (бот) добавила в README свой пласт команд — не скиллов
`/planerka:...`, а подкоманд CLI `run.py` (`бот`, `проверить-бота`,
`узнать-chat-id`), их флагов (`--обойти-блокировку` и старые
`--папка`/`--пересобрать`) и имён переменных окружения (`TELEGRAM_BOT_TOKEN`,
`TELEGRAM_CHAT_ID`). Ровно та же болезнь могла повториться на новом
материале — README мог бы звать `run.py запустить-бота` или переменную
`TG_BOT_TOKEN`, которых в коде нет, — поэтому сторож расширен и на них.
"""
import re
import subprocess
import sys
from pathlib import Path

КОРЕНЬ = Path(__file__).resolve().parents[1]
README = (КОРЕНЬ / "README.md").read_text(encoding="utf-8")

# Команда в тексте: в обратных кавычках (`/planerka:имя`) или строкой в блоке
# кода — блок установки написан именно так, и мимо сторожа он проходить не
# должен.
В_КАВЫЧКАХ = re.compile(r"`/([^`\s]+)")
СТРОКОЙ = re.compile(r"^/(\S+)", re.MULTILINE)


def команды_из_readme() -> list[str]:
    return В_КАВЫЧКАХ.findall(README) + СТРОКОЙ.findall(README)


def имена_скиллов() -> set[str]:
    имена = {п.name for п in (КОРЕНЬ / "planerka" / "skills").iterdir() if п.is_dir()}
    assert имена, "в плагине нет ни одного скилла"
    return имена


def test_каждая_команда_из_readme_существует():
    встроенные = {"plugin"}  # /plugin marketplace add, /plugin install
    скиллы = имена_скиллов()
    выдуманные = []
    for слово in команды_из_readme():
        if слово in встроенные:
            continue
        плагин, _, имя = слово.partition(":")
        if плагин != "planerka" or имя not in скиллы:
            выдуманные.append(слово)
    assert not выдуманные, f"README зовёт то, чего в плагине нет: {выдуманные}"


def test_установка_идёт_из_репозитория_а_не_из_папки_автора():
    assert "Natalyyyy/planerka" in README
    assert "~/Projects" not in README


# --- CLI бота: подкоманды, флаги, переменные окружения


# Слово сразу после `run.py" в блоках кода README — подкоманда CLI
# (`темы`, `план`, `бот`, `проверить-бота`, `узнать-chat-id`), которая
# обязана быть настоящим значением `run.КОМАНДЫ`. Флаги (`--папка` и
# т. п.) сюда не попадают — они идут вторым, третьим и т. д. словом в той
# же строке, а не сразу после `run.py"`.
ПОДКОМАНДА_RUN_PY = re.compile(r'run\.py"\s+(\S+)')


def подкоманды_run_py_из_readme() -> list[str]:
    return ПОДКОМАНДА_RUN_PY.findall(README)


def test_подкоманды_run_py_из_readme_существуют():
    from planerka import run

    найдено = подкоманды_run_py_из_readme()
    assert найдено, "README не зовёт run.py ни разу — блок про бота потерялся"
    выдуманные = [слово for слово in найдено if слово not in run.КОМАНДЫ]
    assert not выдуманные, f"README зовёт подкоманду run.py, которой нет в run.КОМАНДЫ: {выдуманные}"


# Все `--флаг`, встречающиеся в README (в тексте или в блоках кода) —
# argparse-опции `run.py`. Один дефис (`-h`) сюда не попадает намеренно:
# README про короткую форму не рассказывает.
ФЛАГ_RUN_PY = re.compile(r"--[\w-]+")


def флаги_из_readme() -> set[str]:
    return set(ФЛАГ_RUN_PY.findall(README))


def test_флаги_из_readme_существуют_в_cli():
    """Прогоняет настоящий `run.py --help` и проверяет, что каждый флаг,
    упомянутый в README, в нём действительно значится — иначе README зовёт
    флаг, которого argparse не знает, и человек получает `error: unrecognized
    arguments` вместо помощи."""
    результат = subprocess.run(
        [sys.executable, str(КОРЕНЬ / "planerka" / "run.py"), "--help"],
        capture_output=True, text=True, timeout=10,
    )
    assert результат.returncode == 0, результат.stderr
    найдено = флаги_из_readme()
    assert найдено, "README не упоминает ни одного флага run.py"
    выдуманные = [флаг for флаг in найдено if флаг not in результат.stdout]
    assert not выдуманные, f"README зовёт флаг, которого нет в CLI: {выдуманные}"


def test_переменные_окружения_бота_из_readme_совпадают_с_кодом():
    """`TELEGRAM_BOT_TOKEN` и `TELEGRAM_CHAT_ID` — имена, которые реально
    читает `run.py` (см. `_ПЕРЕМЕННАЯ_ТОКЕНА`/`_ПЕРЕМЕННАЯ_CHAT_ID`). Опечатка
    вида `TELEGRAM_TOKEN` в README даёт человеку рабочий на вид `.env`,
    который бот никогда не прочитает."""
    from planerka import run

    настоящие = {run._ПЕРЕМЕННАЯ_ТОКЕНА, run._ПЕРЕМЕННАЯ_CHAT_ID}
    упомянутые = set(re.findall(r"\bTELEGRAM_[A-Z_]+\b", README))
    assert упомянутые, "README не упоминает ни одной переменной окружения бота"
    выдуманные = упомянутые - настоящие
    assert not выдуманные, f"README называет переменные, которых нет в коде: {выдуманные}"
    пропущенные = настоящие - упомянутые
    assert not пропущенные, f"README не называет переменные, которые реально нужны: {пропущенные}"
