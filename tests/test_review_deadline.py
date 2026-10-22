"""Регрессии по находкам 5, 7, 8 и 12 отчёта ревью."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock

import pytest

from planerka.bot.процесс import _файл_блокировки, запустить_бота
from planerka.bot.api import ОшибкаСети

ТОКЕН = "444444:ВЫДУМАННЫЙ-ТОКЕН-НЕ-НАСТОЯЩИЙ"
CHAT_ID = 999999
СЕЙЧАС = datetime(2026, 9, 9, 20, 0, 1)


@pytest.fixture(autouse=True)
def изолированный_дом(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))


@pytest.fixture
def мир(tmp_path):
    заметки = tmp_path / "notes"
    недели = заметки / "недели"
    недели.mkdir(parents=True)
    блоки = tmp_path / "blocks"
    (блоки / "sources").mkdir(parents=True)
    (блоки / "platforms").mkdir()
    (блоки / "core.md").write_text("ядро", encoding="utf-8")
    (блоки / "core-план.md").write_text("ядро плана", encoding="utf-8")
    файл = недели / "неделя – 2026-09-07.md"
    файл.write_text(
        "<!-- planerka-bank: 11111111111111111111111111111111 -->\n"
        "## Банк тем\n\n- [x] Взятая тема · откуда: чат\n",
        encoding="utf-8",
    )
    return заметки, блоки, файл


def _запустить(заметки, блоки, *, отправить=None, получить=None, итераций=1, дедлайн="среда, 20:00"):
    config = {"модель": "claude-sonnet-5"}
    if дедлайн is not None:
        config["дедлайн_такта_б"] = дедлайн
    return запустить_бота(
        ТОКЕН, CHAT_ID, заметки,
        config,
        блоки,
        получить_обновления=получить or Mock(return_value=[]),
        отправить_сообщение=отправить or Mock(),
        now=lambda: СЕЙЧАС,
        макс_итераций=итераций,
    )


def _utf16_units(text: str) -> int:
    return len(text.encode("utf-16-le")) // 2


def _подменить_cli(monkeypatch, ответы):
    очередь = iter(ответы)
    вызовы = []

    def cli(*args, **kwargs):
        вызовы.append((args, kwargs))
        ответ = next(очередь)
        if isinstance(ответ, BaseException):
            raise ответ
        if isinstance(ответ, subprocess.CompletedProcess):
            return ответ
        if isinstance(ответ, tuple):
            код, stdout, stderr = ответ
            return subprocess.CompletedProcess(args[0], код, stdout, stderr)
        return subprocess.CompletedProcess(args[0], 0, ответ, "")

    monkeypatch.setattr("planerka.runner.llm.subprocess.run", cli)
    return вызовы


def test_два_запуска_в_одной_папке_сериализованы_всё_время_работы(мир):
    заметки, блоки, _ = мир
    результат_второго = []

    def опрос(*args, **kwargs):
        путь_метаданных = _файл_блокировки(заметки)
        путь_метаданных.unlink()
        код = (
            "import sys\n"
            "from datetime import datetime\n"
            "from pathlib import Path\n"
            "from planerka.bot.процесс import _захватить_блокировку\n"
            "try:\n"
            "    _захватить_блокировку(Path(sys.argv[1]), now=datetime.now())\n"
            "    print('acquired')\n"
            "except RuntimeError:\n"
            "    print('busy')\n"
        )
        дочерний = subprocess.run(
            [sys.executable, "-c", код, str(заметки)],
            capture_output=True, text=True, env=os.environ.copy(), check=False,
        )
        результат_второго.append(дочерний.stdout.strip())
        return []

    _запустить(заметки, блоки, получить=опрос, дедлайн=None)

    assert результат_второго == ["busy"]


def test_временный_сбой_llm_повторяет_takt_b_и_успех_закрывает_дедлайн(мир, monkeypatch):
    заметки, блоки, файл = мир
    cli = _подменить_cli(monkeypatch, [
        subprocess.TimeoutExpired(["claude"], timeout=900),
        "## Неделя по дням\n\nПн — Взятая тема",
    ])

    отправить = Mock()
    _запустить(
        заметки, блоки, отправить=отправить,
        итераций=3,
    )

    содержимое = файл.read_text(encoding="utf-8")
    assert "## Неделя по дням" in содержимое
    assert "Пн — Взятая тема" in содержимое
    assert len(cli) == 2
    assert отправить.call_count == 1
    assert "план собран" in отправить.call_args.args[2].lower()
    marker = json.loads((файл.parent / f"{файл.stem}.дедлайн-обработан.json").read_text(encoding="utf-8"))
    assert marker["уведомлён"] is True


def test_временный_сбой_llm_ограничен_тремя_попытками(мир, monkeypatch):
    заметки, блоки, файл = мир

    очередь_cli = _подменить_cli(monkeypatch, [
        subprocess.TimeoutExpired(["claude"], timeout=900),
        subprocess.TimeoutExpired(["claude"], timeout=900),
        subprocess.TimeoutExpired(["claude"], timeout=900),
    ])
    отправить = Mock()
    _запустить(
        заметки, блоки, отправить=отправить,
        итераций=5,
    )

    marker = json.loads((файл.parent / f"{файл.stem}.дедлайн-обработан.json").read_text(encoding="utf-8"))
    assert len(очередь_cli) == 3
    assert отправить.call_count == 1
    assert "после 3 попыток" in отправить.call_args.args[2]
    assert marker["уведомлён"] is True


def test_cli_429_и_500_повторяются_через_реальный_run_claude(мир, monkeypatch):
    заметки, блоки, файл = мир
    cli = _подменить_cli(monkeypatch, [
        (1, "", "429 rate limit"),
        (1, "", "500 upstream unavailable"),
        (0, "## Неделя по дням\n\nПн — восстановленная тема", ""),
    ])
    отправить = Mock()

    _запустить(заметки, блоки, отправить=отправить, итераций=4)

    assert len(cli) == 3
    assert "Пн — восстановленная тема" in файл.read_text(encoding="utf-8")
    assert отправить.call_count == 1
    assert "восстановленная тема" in отправить.call_args.args[2]


def test_новая_версия_банка_повторно_обрабатывает_тот_же_дедлайн(мир, monkeypatch):
    заметки, блоки, файл = мир
    cli = _подменить_cli(monkeypatch, ["## Неделя по дням\n\nПн — тема", "## Неделя по дням\n\nПн — тема"])
    отправить = Mock()
    _запустить(заметки, блоки, отправить=отправить)

    файл.write_text(
        файл.read_text(encoding="utf-8").replace("11111111111111111111111111111111", "22222222222222222222222222222222"),
        encoding="utf-8",
    )
    _запустить(заметки, блоки, отправить=отправить)

    assert len(cli) == 2
    assert отправить.call_count == 2


def test_дедлайн_отправляет_содержимое_плана_в_пределе_telegram(мир, monkeypatch):
    заметки, блоки, _ = мир
    _подменить_cli(monkeypatch, ["## Неделя по дням\n\nПн — важная тема"])
    отправить = Mock()

    _запустить(заметки, блоки, отправить=отправить)

    текст = отправить.call_args.args[2]
    assert "Пн — важная тема" in текст
    assert len(текст) <= 4096


def test_длинный_план_отправляется_полностью_частями_в_лимите_utf16(мир, monkeypatch):
    заметки, блоки, _ = мир
    _подменить_cli(monkeypatch, ["## Неделя по дням\n\n" + "План. " * 1200])
    отправить = Mock()

    _запустить(заметки, блоки, отправить=отправить)

    части = [вызов.args[2] for вызов in отправить.call_args_list]
    assert len(части) > 1
    assert all(_utf16_units(часть) <= 4096 for часть in части)
    assert "".join(части).count("План.") == 1200


def test_повторная_отправка_продолжает_с_недоставленной_части(мир, monkeypatch):
    заметки, блоки, _ = мир
    cli = _подменить_cli(monkeypatch, ["## Неделя по дням\n\n" + "🪐" * 3000])
    отправить = Mock(side_effect=[None, ОшибкаСети("сеть упала"), None])

    _запустить(заметки, блоки, отправить=отправить, итераций=2)

    assert len(cli) == 1
    assert отправить.call_count == 3
    assert отправить.call_args_list[1].args[2] == отправить.call_args_list[2].args[2]
    assert отправить.call_args_list[0].args[2] != отправить.call_args_list[1].args[2]
