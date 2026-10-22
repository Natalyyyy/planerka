"""Второй круг: авторизация, миграции и сбои после успешного эффекта."""
import json
import os
from pathlib import Path
from unittest.mock import Mock

import pytest

from test_review_deadline import мир, изолированный_дом, _запустить, _подменить_cli, CHAT_ID
from planerka.bot.api import ОшибкаСети
from planerka.bot.отправка import отправить_банк_тем
from planerka.bot.приём import принять_нажатие
from planerka.bot.темы import идентификатор
from planerka.runner.weeks import версия_банка


@pytest.mark.parametrize('sender,chat', [(42, CHAT_ID), (CHAT_ID, 42), (None, CHAT_ID), (CHAT_ID, None), (True, CHAT_ID), (CHAT_ID, -42)])
def test_round2_1_reject_foreign_callback(мир, monkeypatch, sender, chat):
    root, blocks, week = мир
    before = week.read_bytes()
    replies = Mock()
    monkeypatch.setattr('planerka.bot.приём.ответить_на_нажатие', replies)
    data = f'2026-09-07:{версия_банка(week.read_text())}:{идентификатор("Взятая тема · откуда: чат")}:n'
    update = {'update_id': 1, 'callback_query': {'id': 'fake', 'data': data,
              'from': {'id': sender}, 'message': {'chat': {'id': chat}}}}
    _запустить(root, blocks, получить=Mock(return_value=[update]), дедлайн=None)
    assert week.read_bytes() == before
    assert replies.call_count == 0


def test_round2_1_owner_replay_after_ack_lost(мир, monkeypatch):
    root, blocks, week = мир
    applied = []
    def ack(*args, **kwargs):
        applied.append(args)
        raise ОшибкаСети('response lost after acceptance')
    monkeypatch.setattr('planerka.bot.приём.ответить_на_нажатие', ack)
    data = f'2026-09-07:{версия_банка(week.read_text())}:{идентификатор("Взятая тема · откуда: чат")}:n'
    update = {'update_id': 1, 'callback_query': {'id': 'fake', 'data': data,
              'from': {'id': CHAT_ID}, 'message': {'chat': {'id': CHAT_ID}}}}
    _запустить(root, blocks, получить=Mock(return_value=[update]), дедлайн=None, итераций=2)
    assert '- [-] Взятая тема' in week.read_text()
    assert len(applied) == 2
    assert 'Уже отмечено' in applied[1][2]


@pytest.mark.parametrize('notified', [True, False])
def test_round2_2_legacy_marker_preserves_completed_plan(мир, monkeypatch, notified):
    root, blocks, week = мир
    week.write_text(week.read_text().split('\n', 1)[1] + '\n## Неделя по дням\nSaved plan\n')
    marker = week.with_name(week.stem + '.дедлайн-обработан.json')
    marker.write_text(json.dumps({'дедлайн': '2026-09-09T20:00:00', 'сообщение': 'Saved notification', 'уведомлён': notified}))
    before = week.read_bytes()
    cli = _подменить_cli(monkeypatch, ['## Неделя по дням\nUnexpected'])
    delivered = []
    def send(*args):
        delivered.append(args[2])
        if len(delivered) == 1:
            raise ОшибкаСети('response lost after delivery')
    _запустить(root, blocks, отправить=send, итераций=2)
    assert cli == []
    assert week.read_bytes() == before
    assert delivered == ([] if notified else ['Saved notification'] * 2)
    state = json.loads(marker.read_text())
    assert state['версия_банка'] == версия_банка(week.read_text())
    assert state['уведомлён'] is True


def test_round2_3_legacy_journal_refreshes_buttons_after_lost_response(мир, monkeypatch):
    root, _, week = мир
    week.write_text('## Банк тем\n- [ ] A\n')
    (week.parent / 'неделя – 2026-08-31.md').write_text(week.read_text())
    journal = week.with_name(week.stem + '.отправлено.json')
    journal.write_text(json.dumps({'отправлено': [идентификатор('A')]}))
    delivered = []
    def send(token, chat, text, rows):
        delivered.append(rows[0][0][1])
        if len(delivered) == 1:
            raise ОшибкаСети('response lost after delivery')
    monkeypatch.setattr('planerka.bot.отправка.отправить_с_кнопками', send)
    monkeypatch.setattr('planerka.bot.приём.ответить_на_нажатие', lambda *a, **k: None)
    with pytest.raises(ОшибкаСети):
        отправить_банк_тем('fake', CHAT_ID, root)
    assert отправить_банк_тем('fake', CHAT_ID, root)['отправлено'] == ['A']
    assert отправить_банк_тем('fake', CHAT_ID, root)['отправлено'] == []
    assert delivered[0] == delivered[1]
    assert принять_нажатие('fake', 'callback', delivered[0], root)['статус'] == 'записано'
    assert принять_нажатие('fake', 'callback', delivered[1], root)['статус'] == 'без_изменений'


@pytest.mark.parametrize('error', [OSError('read failed'), UnicodeDecodeError('utf8', b'\xff', 0, 1, 'invalid')])
def test_round2_4_plan_read_failure_does_not_regenerate(мир, monkeypatch, error):
    root, blocks, week = мир
    cli = _подменить_cli(monkeypatch, ['## Неделя по дням\nSaved plan'] * 3)
    read_text = Path.read_text
    def read(path, *args, **kwargs):
        # Fault only when reading the newly saved plan for the notification.
        import inspect
        if path == week and inspect.currentframe().f_back.f_code.co_name == '_раздел_плана':
            raise error
        return read_text(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'read_text', read)
    delivered = []
    def send(*args):
        delivered.append(args[2])
        if len(delivered) == 1:
            raise ОшибкаСети('response lost after delivery')
    _запустить(root, blocks, отправить=send, итераций=3)
    assert len(cli) == 1
    assert 'Saved plan' in week.read_text()
    assert len(delivered) == 2
    assert delivered[0] == delivered[1]
    assert 'план собран' in delivered[0]
    marker = json.loads(week.with_name(week.stem + '.дедлайн-обработан.json').read_text())
    assert marker['сборка_готова'] is True
    assert marker['уведомлён'] is True


@pytest.mark.parametrize('new_bank,new_deadline', [(True, False), (False, True)])
def test_round2_2_legacy_marker_does_not_close_new_generation_or_deadline(мир, monkeypatch, new_bank, new_deadline):
    root, blocks, week = мир
    if not new_bank:
        week.write_text(week.read_text().split('\n', 1)[1])
    marker = week.with_name(week.stem + '.дедлайн-обработан.json')
    marker.write_text(json.dumps({'дедлайн': '2026-09-09T19:00:00' if new_deadline else '2026-09-09T20:00:00',
                                 'сообщение': 'Old notification', 'уведомлён': True}))
    cli = _подменить_cli(monkeypatch, ['## Неделя по дням\nNew plan'])
    sent = Mock()
    _запустить(root, blocks, отправить=sent, итераций=2)
    assert len(cli) == 1
    assert sent.call_count == 1
    assert 'New plan' in sent.call_args.args[2]


def test_round2_2_migration_write_error_preserves_legacy_plan(мир, monkeypatch):
    root, blocks, week = мир
    week.write_text(week.read_text().split('\n', 1)[1] + '\n## Неделя по дням\nSaved plan')
    marker = week.with_name(week.stem + '.дедлайн-обработан.json')
    marker.write_text(json.dumps({'дедлайн': '2026-09-09T20:00:00', 'сообщение': 'Saved', 'уведомлён': True}))
    before = week.read_bytes()
    cli = _подменить_cli(monkeypatch, [])
    replace = os.replace
    failures = []
    def fail_replace(path, target):
        if target == marker:
            failures.append(target)
            raise OSError('write failed')
        return replace(path, target)
    monkeypatch.setattr(os, 'replace', fail_replace)
    sent = Mock()
    _запустить(root, blocks, отправить=sent, итераций=2)
    assert not cli
    assert not sent.called
    assert week.read_bytes() == before
    assert failures == [marker, marker]
    assert "версия_банка" not in json.loads(marker.read_text())
