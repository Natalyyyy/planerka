import json
import subprocess
from urllib.error import HTTPError

import pytest

from planerka import run
from bot import api


@pytest.fixture(autouse=True)
def не_запускать_генератор(monkeypatch):
    def unexpected_subprocess(*args, **kwargs):
        raise AssertionError("CLI досылки не должна запускать внешний генератор")

    monkeypatch.setattr(subprocess, "run", unexpected_subprocess)


@pytest.fixture
def отправка_мира(tmp_path, monkeypatch):
    notes = tmp_path / "notes"
    weeks = notes / "недели"
    weeks.mkdir(parents=True)
    (notes / "конфиг.json").write_text(json.dumps({
        "модель": "claude-sonnet-5",
        "папка_заметок": str(notes),
        "источники": [],
        "площадки": [],
    }), encoding="utf-8")
    (notes / ".env").write_text(
        "TELEGRAM_BOT_TOKEN=123456:TESTTOKEN\nTELEGRAM_CHAT_ID=42\n",
        encoding="utf-8",
    )
    (weeks / "неделя – 2026-09-07.md").write_text(
        "## Банк тем\n\n"
        "- [ ] Первая тема · откуда: тест\n"
        "- [ ] Вторая тема · откуда: тест\n"
        "- [ ] Третья тема · откуда: тест\n",
        encoding="utf-8",
    )
    отправлено = []
    сбой_на_второй = True

    class Ответ:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def read(self):
            return json.dumps({"ok": True, "result": {"message_id": len(отправлено), "chat": {"id": 42}}}).encode()

    def urlopen(request, timeout):
        nonlocal сбой_на_второй
        данные = json.loads(request.data)
        текст = данные["text"]
        отправлено.append(текст)
        if сбой_на_второй and len(отправлено) == 2:
            сбой_на_второй = False
            raise HTTPError(request.full_url, 400, "bad request", {}, None)
        return Ответ()

    monkeypatch.setattr(api, "urlopen", urlopen)
    return notes, отправлено


def test_cli_resumes_partial_send_and_skips_already_sent_topics(отправка_мира, capsys):
    notes, отправлено = отправка_мира

    with pytest.raises(SystemExit) as error:
        run.main(["дослать-темы", "--папка", str(notes)])
    assert error.value.code == 1
    assert len(отправлено) == 2
    assert "ушло 1 тем из 3" in capsys.readouterr().err

    run.main(["дослать-темы", "--папка", str(notes)])
    assert len(отправлено) == 4
    assert "Дослано тем: 2 из 3" in capsys.readouterr().out
    assert отправлено == ["Первая тема", "Вторая тема", "Вторая тема", "Третья тема"]

    run.main(["дослать-темы", "--папка", str(notes)])
    assert len(отправлено) == 4
    assert "уже отправлялись" in capsys.readouterr().out

    состояния = list((notes / "недели").glob("*.отправлено.json"))
    assert len(состояния) == 1
    assert len(json.loads(состояния[0].read_text(encoding="utf-8"))["отправлено"]) == 3


def test_cli_with_empty_bank_succeeds_without_http_or_journal(отправка_мира, capsys):
    notes, отправлено = отправка_мира
    week = next((notes / "недели").glob("неделя – *.md"))
    original = (
        "## Банк тем\n\n"
        "- [x] Уже решена · откуда: тест\n"
        "- [-] Отклонена · откуда: тест\n"
    ).encode()
    week.write_bytes(original)

    run.main(["дослать-темы", "--папка", str(notes)])

    assert "отправлять нечего" in capsys.readouterr().out
    assert отправлено == []
    assert week.read_bytes() == original
    assert list((notes / "недели").glob("*.отправлено.json")) == []


def test_cli_without_credentials_reports_configuration_error(отправка_мира, monkeypatch, capsys):
    notes, отправлено = отправка_мира
    (notes / ".env").unlink()
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)

    with pytest.raises(SystemExit) as error:
        run.main(["дослать-темы", "--папка", str(notes)])

    assert error.value.code == 1
    assert "TELEGRAM_BOT_TOKEN и TELEGRAM_CHAT_ID" in capsys.readouterr().err
    assert отправлено == []
    assert list((notes / "недели").glob("*.отправлено.json")) == []


def test_cli_first_http_error_is_reported_without_marking_any_topic(отправка_мира, monkeypatch, capsys):
    notes, отправлено = отправка_мира

    def fail_first_request(request, timeout):
        raise HTTPError(request.full_url, 400, "bad request", {}, None)

    monkeypatch.setattr(api, "urlopen", fail_first_request)
    with pytest.raises(SystemExit) as error:
        run.main(["дослать-темы", "--папка", str(notes)])

    assert error.value.code == 1
    assert "Не удалось дослать банк тем" in capsys.readouterr().err
    assert отправлено == []
    assert list((notes / "недели").glob("*.отправлено.json")) == []


def test_cli_partial_resume_skips_marked_topic_and_preserves_week_bytes(отправка_мира, capsys):
    notes, отправлено = отправка_мира
    week = next((notes / "недели").glob("неделя – *.md"))
    week.write_text(
        "## Банк тем\n\n"
        "- [x] Уже отмечена · откуда: тест\n"
        "- [ ] Первая тема · откуда: тест\n"
        "- [ ] Вторая тема · откуда: тест\n",
        encoding="utf-8",
    )
    original = week.read_bytes()

    with pytest.raises(SystemExit):
        run.main(["дослать-темы", "--папка", str(notes)])
    assert week.read_bytes() == original
    assert "ушло 1 тем из 2" in capsys.readouterr().err

    run.main(["дослать-темы", "--папка", str(notes)])

    assert отправлено == ["Первая тема", "Вторая тема", "Вторая тема"]
    assert "Уже отмечена" not in отправлено
    assert week.read_bytes() == original
    assert "Дослано тем: 1 из 2" in capsys.readouterr().out
