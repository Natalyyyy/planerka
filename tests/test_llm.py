import subprocess
from unittest.mock import MagicMock, patch

import pytest

from planerka.runner.llm import run_claude


def test_happy_возвращает_stdout():
    with patch("planerka.runner.llm.subprocess.run") as run:
        run.return_value = MagicMock(returncode=0, stdout="ответ модели", stderr="")
        результат = run_claude("промпт", model="claude-sonnet-5")
    assert результат == "ответ модели"


def test_ненулевой_код_возврата_даёт_RuntimeError_с_кодом_и_stderr():
    with patch("planerka.runner.llm.subprocess.run") as run:
        run.return_value = MagicMock(returncode=2, stdout="", stderr="модель недоступна")
        with pytest.raises(RuntimeError) as исключение:
            run_claude("промпт", model="claude-sonnet-5")
    assert "2" in str(исключение.value)
    assert "модель недоступна" in str(исключение.value)


def test_таймаут_пробрасывается_наружу_а_не_глотается():
    with patch("planerka.runner.llm.subprocess.run") as run:
        run.side_effect = subprocess.TimeoutExpired(cmd="claude", timeout=5)
        with pytest.raises(subprocess.TimeoutExpired):
            run_claude("промпт", model="claude-sonnet-5", timeout_sec=5)


def test_модель_явно_в_команде_и_промпт_через_stdin_а_не_argv():
    with patch("planerka.runner.llm.subprocess.run") as run:
        run.return_value = MagicMock(returncode=0, stdout="ок", stderr="")
        run_claude("секретный промпт длиной с мегабайт", model="claude-opus-5")
    аргументы, именованные = run.call_args
    команда = аргументы[0]
    assert "--model" in команда
    assert команда[команда.index("--model") + 1] == "claude-opus-5"
    assert "секретный промпт длиной с мегабайт" not in команда
    assert именованные.get("input") == "секретный промпт длиной с мегабайт"
