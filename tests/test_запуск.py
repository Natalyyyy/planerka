"""Прогон из установленного плагина, а не из клона репозитория.

После настоящей установки каталог плагина лежит где-то в кэше Claude Code, и
родителя пакета на `sys.path` нет: `import planerka` даёт
ModuleNotFoundError. Живой цикл этого не поймал, потому что шёл из клона
репозитория, где родитель случайно оказывался в пути.

Здесь установка имитируется: каталог плагина копируется в чужое место, вызов
идёт из третьего каталога, а Claude CLI подменяется заглушкой — проверяется
запуск, а не модель.
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ПЛАГИН = Path(__file__).resolve().parents[1] / "planerka"
СКИЛЛ = (ПЛАГИН / "skills" / "planerka" / "SKILL.md").read_text(encoding="utf-8")

ЗАГЛУШКА = """#!/bin/sh
stdin=$(cat)
case "$stdin" in
  *"Взятые темы"*) printf '## Неделя по дням\\n\\nПн — Тема из заглушки\\n' ;;
  *) printf '## Банк тем\\n\\n- [x] Тема из заглушки · откуда: заглушка\\n' ;;
esac
"""


@pytest.fixture
def установка(tmp_path):
    """Каталог плагина в чужом месте, папка заметок, заглушка вместо claude."""
    корень = tmp_path / "кэш-плагинов" / "planerka-9f3a1c"
    корень.parent.mkdir(parents=True)
    shutil.copytree(ПЛАГИН, корень,
                    ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"))

    заметки = tmp_path / "мои-заметки"
    заметки.mkdir()
    (заметки / "конфиг.json").write_text(json.dumps({
        "папка_заметок": str(заметки),
        "язык": "русский",
        "модель": "claude-sonnet-5",
        "источники": [],
        "площадки": [],
    }, ensure_ascii=False), encoding="utf-8")

    бин = tmp_path / "бин"
    бин.mkdir()
    (бин / "claude").write_text(ЗАГЛУШКА, encoding="utf-8")
    (бин / "claude").chmod(0o755)

    дом = tmp_path / "дом"
    дом.mkdir()
    чужой_cwd = tmp_path / "чужой-каталог"
    чужой_cwd.mkdir()

    def запустить(*аргументы):
        окружение = {**os.environ,
                     "PATH": f"{бин}:{os.environ['PATH']}",
                     "HOME": str(дом)}
        окружение.pop("PYTHONPATH", None)
        # Такт «темы» теперь сам шлёт банк в телеграм, если видит токен и
        # chat_id в окружении (см. planerka/run.py, часть 4). Эти тесты
        # проверяют установку и запуск, а не сеть — если на машине, где
        # гоняются тесты, эти переменные вдруг реально стоят (например,
        # для другого процесса), такт «темы» тут не должен внезапно
        # получить право ходить в настоящий Телеграм.
        окружение.pop("TELEGRAM_BOT_TOKEN", None)
        окружение.pop("TELEGRAM_CHAT_ID", None)
        return subprocess.run(
            [sys.executable, str(корень / "run.py"), *аргументы],
            cwd=чужой_cwd, env=окружение,
            capture_output=True, text=True, timeout=120,
        )

    return запустить, заметки, дом


def test_такт_а_идёт_из_установленного_плагина(установка):
    запустить, заметки, _ = установка
    готово = запустить("темы", "--папка", str(заметки))

    assert готово.returncode == 0, готово.stderr
    файлы = list((заметки / "недели").glob("неделя – *.md"))
    assert len(файлы) == 1
    assert "Тема из заглушки" in файлы[0].read_text(encoding="utf-8")
    assert файлы[0].name in готово.stdout


def test_второй_запуск_находит_папку_по_указателю(установка):
    запустить, заметки, дом = установка
    assert запустить("темы", "--папка", str(заметки)).returncode == 0

    готово = запустить("план")

    assert готово.returncode == 0, готово.stderr
    файл = next((заметки / "недели").glob("неделя – *.md"))
    assert "## Неделя по дням" in файл.read_text(encoding="utf-8")


def test_без_папки_и_без_указателя_понятная_ошибка(установка):
    запустить, _, _ = установка
    готово = запустить("темы")

    assert готово.returncode != 0
    assert "--папка" in готово.stderr


def test_в_папке_нет_конфига_понятная_ошибка(установка, tmp_path):
    запустить, _, _ = установка
    пустая = tmp_path / "не-настроено"
    пустая.mkdir()

    готово = запустить("темы", "--папка", str(пустая))

    assert готово.returncode != 0
    assert "конфиг.json" in готово.stderr


def test_неизвестный_такт_не_запускается(установка):
    запустить, заметки, _ = установка
    готово = запустить("погнали", "--папка", str(заметки))

    assert готово.returncode != 0


def test_скилл_даёт_исполнимую_команду_с_корнем_плагина():
    """Скилл обязан содержать команду, которую можно выполнить, а не отсылку
    к функции питона: «зовёт takt_a из takt_a.py» после установки не
    выполняется никак."""
    assert "${CLAUDE_PLUGIN_ROOT}/run.py" in СКИЛЛ
    assert (ПЛАГИН / "run.py").exists()
    for такт in ("темы", "план"):
        assert f'run.py" {такт}' in СКИЛЛ, f"в скилле нет команды такта «{такт}»"


def _старый_питон() -> str | None:
    """Интерпретатор младше 3.10, если он есть в системе.

    На маке `python3` из коробки — 3.9, и человек по инструкции запустит
    именно его. Код планёрки написан на синтаксисе 3.10 (`date | None`), и
    без проверки версии человек получает TypeError из середины импорта,
    по которому невозможно понять, что делать.
    """
    for кандидат in ("/usr/bin/python3", "/usr/bin/python3.9", "/usr/local/bin/python3.9"):
        if not Path(кандидат).exists():
            continue
        готово = subprocess.run([кандидат, "-c", "import sys; print(sys.version_info[:2])"],
                                capture_output=True, text=True)
        if готово.returncode == 0 and eval(готово.stdout) < (3, 10):
            return кандидат
    return None


@pytest.mark.skipif(_старый_питон() is None, reason="в системе нет питона младше 3.10")
def test_старый_питон_говорит_что_нужна_версия(установка, tmp_path):
    запустить, заметки, _ = установка
    старый = _старый_питон()
    корень = next(tmp_path.glob("кэш-плагинов/*"))

    готово = subprocess.run([старый, str(корень / "run.py"), "темы", "--папка", str(заметки)],
                            capture_output=True, text=True, timeout=120)

    assert готово.returncode != 0
    assert "3.10" in готово.stderr
    assert "TypeError" not in готово.stderr
