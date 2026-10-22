"""Регрессии двух находок второго ревью; внешние эффекты без сети."""
import json
import os
import subprocess

import pytest

from test_review_deadline import мир, изолированный_дом, _запустить
from planerka.bot.api import ОшибкаСети


def marker(week):
    return json.loads(week.with_name(week.stem + '.дедлайн-обработан.json').read_text())


@pytest.mark.parametrize('conflicts', [1, 4])
def test_selection_conflict_retries_current_choices(мир, monkeypatch, conflicts):
    root, blocks, week = мир
    calls = []
    delivered = []

    def cli(*args, **kwargs):
        calls.append(kwargs['input'])
        if len(calls) <= conflicts:
            text = week.read_text()
            old = 'Взятая тема' if len(calls) == 1 else f'Topic {len(calls)-1}'
            week.write_text(text.replace(old, f'Topic {len(calls)}'))
        return subprocess.CompletedProcess(args[0], 0, f'## Неделя по дням\nPlan {len(calls)}', '')

    def send(*args):
        delivered.append(args[2])
        if len(delivered) == 1:
            raise ОшибкаСети('response lost after delivery')

    monkeypatch.setattr('planerka.runner.llm.subprocess.run', cli)
    _запустить(root, blocks, отправить=send)
    assert marker(week)['сборка_готова'] is False
    assert delivered == []
    assert '## Неделя по дням' not in week.read_text()
    _запустить(root, blocks, отправить=send, итераций=conflicts + 2)
    assert len(calls) == conflicts + 1
    assert f'Topic {conflicts}' in calls[-1]
    assert f'Plan {conflicts + 1}' in week.read_text()
    assert len(delivered) == 2
    assert delivered[0] == delivered[1]
    assert 'план собран' in delivered[0]
    assert marker(week)['уведомлён'] is True


@pytest.mark.parametrize('applied', [False, True])
def test_archive_failure_preserves_saved_plan(мир, monkeypatch, applied):
    root, blocks, week = мир
    week.write_text(week.read_text() + '- [-] Rejected topic\n')
    archive = root / 'отклонённые.md'
    calls, writes, delivered = [], [], []
    replace = os.replace

    def cli(*args, **kwargs):
        calls.append(kwargs['input'])
        return subprocess.CompletedProcess(args[0], 0, '## Неделя по дням\nSaved plan', '')

    def replace_with_failure(source, target):
        if target == week:
            writes.append(target)
        if target == archive:
            if applied:
                replace(source, target)
            raise OSError('archive response lost' if applied else 'archive unavailable')
        return replace(source, target)

    def send(*args):
        delivered.append(args[2])
        if len(delivered) == 1:
            raise ОшибкаСети('response lost after delivery')

    monkeypatch.setattr('planerka.runner.llm.subprocess.run', cli)
    monkeypatch.setattr(os, 'replace', replace_with_failure)
    _запустить(root, blocks, отправить=send, итераций=4)
    assert len(calls) == 1
    assert len(writes) == 1
    assert 'Saved plan' in week.read_text()
    assert '- [-] Rejected topic' in week.read_text()
    assert len(delivered) == 2
    assert delivered[0] == delivered[1]
    assert 'план собран' in delivered[0]
    assert 'архив' in delivered[0].lower()
    assert 'Saved plan' in delivered[0]
    assert marker(week)['сборка_готова'] is True
    assert marker(week)['уведомлён'] is True
    if applied:
        assert archive.read_text().count('Rejected topic') == 1
