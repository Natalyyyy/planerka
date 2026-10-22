"""Offline regressions for concurrent archive updates and topic delivery."""
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path
from threading import Event
import os

import pytest

from planerka.runner.takt_b import _дописать_отклонённые
from planerka.bot import отправка
from planerka.bot.api import ОшибкаСети


DAY = date(2026, 10, 19)


@pytest.mark.parametrize('existing', [False, True])
def test_archive_parallel_updates_keep_both_topics(tmp_path, monkeypatch, existing):
    archive = tmp_path / 'отклонённые.md'
    if existing:
        archive.write_text('# Отклонённые темы\n- Existing\n')
    entered, second_done = Event(), Event()
    replace = os.replace

    def delayed_replace(source, target):
        if target == archive and '- Topic A' in Path(source).read_text():
            entered.set()
            second_done.wait(0.5)
        return replace(source, target)

    monkeypatch.setattr(os, 'replace', delayed_replace)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(_дописать_отклонённые, tmp_path, ['Topic A'], DAY)
        assert entered.wait(2)
        second = pool.submit(_дописать_отклонённые, tmp_path, ['Topic B'], DAY)
        second.add_done_callback(lambda _: second_done.set())
        first.result(timeout=3)
        second.result(timeout=3)
    text = archive.read_text()
    assert text.count('- Topic A') == 1
    assert text.count('- Topic B') == 1
    if existing:
        assert '- Existing' in text
    _дописать_отклонённые(tmp_path, ['Topic A', 'Topic B'], DAY)
    assert archive.read_text() == text


@pytest.mark.parametrize('applied', [False, True])
def test_archive_retry_after_replace_failure(tmp_path, monkeypatch, applied):
    archive = tmp_path / 'отклонённые.md'
    replace = os.replace

    def fail(source, target):
        if applied:
            replace(source, target)
        raise OSError('storage acknowledgement lost')

    with monkeypatch.context() as patch:
        patch.setattr(os, 'replace', fail)
        with pytest.raises(OSError):
            _дописать_отклонённые(tmp_path, ['Topic A'], DAY)
    _дописать_отклонённые(tmp_path, ['Topic A', 'Topic B'], DAY)
    text = archive.read_text()
    assert text.count('- Topic A') == text.count('- Topic B') == 1


@pytest.fixture
def bank(tmp_path):
    folder = tmp_path / 'недели'
    folder.mkdir()
    (folder / 'неделя – 2026-10-19.md').write_text('## Банк тем\n- [ ] Topic A\n- [ ] Topic B\n')
    return tmp_path


def test_parallel_delivery_serializes_entire_batch(bank, monkeypatch):
    entered, second_done = Event(), Event()
    delivered = []

    def send(token, chat, text, buttons):
        delivered.append(text)
        if len(delivered) == 1:
            entered.set()
            second_done.wait(0.5)

    monkeypatch.setattr(отправка, 'отправить_с_кнопками', send)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(отправка.отправить_банк_тем, 'test', 1, bank)
        assert entered.wait(2)
        second = pool.submit(отправка.отправить_банк_тем, 'test', 1, bank)
        second.add_done_callback(lambda _: second_done.set())
        results = [first.result(timeout=3), second.result(timeout=3)]
    assert delivered == ['Topic A', 'Topic B']
    assert results[0]['отправлено'] == ['Topic A', 'Topic B']
    assert results[1]['пропущено'] == ['Topic A', 'Topic B']
    assert results[1]['отправлено'] == []


@pytest.mark.parametrize('applied', [False, True])
def test_delivery_releases_lock_after_uncertain_response(bank, monkeypatch, applied):
    delivered = []
    calls = []

    def send(token, chat, text, buttons):
        calls.append(text)
        if len(calls) == 2:
            if applied:
                delivered.append(text)
            raise ОшибкаСети('response lost')
        delivered.append(text)

    monkeypatch.setattr(отправка, 'отправить_с_кнопками', send)
    with pytest.raises(ОшибкаСети) as error:
        отправка.отправить_банк_тем('test', 1, bank)
    assert getattr(error.value, отправка.ПОЛЕ_УШЕДШИХ) == ['Topic A']
    with ThreadPoolExecutor(max_workers=1) as pool:
        result = pool.submit(отправка.отправить_банк_тем, 'test', 1, bank).result(timeout=3)
    assert result['пропущено'] == ['Topic A']
    assert result['отправлено'] == ['Topic B']
    # Bot API has no idempotency key: a lost response remains ambiguous.
    assert delivered == ['Topic A', 'Topic B', 'Topic B'] if applied else delivered == ['Topic A', 'Topic B']
