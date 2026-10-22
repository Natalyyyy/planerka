from datetime import date
from pathlib import Path

import pytest

from planerka.bot.отправка import отправить_банк_тем
from planerka.bot.приём import принять_нажатие
from planerka.bot.темы import идентификатор
from planerka.runner.takt_a import takt_a


@pytest.fixture
def банк(tmp_path, monkeypatch):
    (tmp_path / 'недели').mkdir()
    файл = tmp_path / 'недели/неделя – 2026-10-12.md'
    файл.write_text('## Банк тем\n- [ ] A\n')
    кнопки = []
    monkeypatch.setattr('planerka.bot.отправка.отправить_с_кнопками',
                        lambda t, c, text, rows: кнопки.append(rows[0][0][1]))
    monkeypatch.setattr('planerka.bot.приём.ответить_на_нажатие', lambda *a, **k: None)
    отправить_банк_тем('test', '1', tmp_path)
    return tmp_path, файл, кнопки[0]


def test_4_старая_кнопка_меняет_свою_неделю(банк):
    root, старый, кнопка = банк
    новый = root / 'недели/неделя – 2026-10-19.md'
    новый.write_text(старый.read_text())
    assert принять_нажатие('test', '1', кнопка, root)['статус'] == 'записано'
    assert '- [x] A' in старый.read_text()
    assert '- [ ] A' in новый.read_text()
    assert len(кнопка.encode()) <= 64
    assert принять_нажатие('test', '2', кнопка, root)['статус'] == 'без_изменений'


def test_4_пересборка_того_же_банка_отменяет_старую_кнопку(банк):
    root, файл, кнопка = банк
    config = {'модель': 'test', 'источники': [], 'площадки': []}
    takt_a(config, root, Path('planerka/blocks'), date(2026, 10, 12),
           зов=lambda *a, **k: '## Банк тем\n- [ ] A\n', пересобрать=True)
    прежде = файл.read_bytes()
    assert принять_нажатие('test', '1', кнопка, root)['статус'] == 'файл_изменился'
    assert файл.read_bytes() == прежде


def test_4_старый_формат_не_угадывает_неделю(банк):
    root, файл, _ = банк
    (root / 'недели/неделя – 2026-10-19.md').write_text(файл.read_text())
    assert принять_нажатие('test', '1', идентификатор('A') + ':b', root)['статус'] == 'файл_изменился'
    assert '- [ ] A' in файл.read_text()


def test_4_удалённая_неделя_не_подменяется_новой(банк):
    root, старый, кнопка = банк
    новый = root / 'недели/неделя – 2026-10-19.md'
    новый.write_text(старый.read_text())
    старый.unlink()
    assert принять_нажатие('test', '1', кнопка, root)['статус'] != 'записано'
    assert '- [ ] A' in новый.read_text()


@pytest.mark.parametrize('данные', ['../../oops:' + 'a'*32 + ':' + 'b'*16 + ':b',
                                  '2026-10-19:broken:' + 'b'*16 + ':b'])
def test_4_битый_префикс_не_меняет_банк(банк, данные):
    root, файл, _ = банк
    прежде = файл.read_bytes()
    assert принять_нажатие('test', '1', данные, root)['статус'] == 'формат_кнопки_неверный'
    assert файл.read_bytes() == прежде


def test_4_повторная_генерация_сбрасывает_журнал_отправки(банк, monkeypatch):
    root, файл, старая = банк
    кнопки = []
    monkeypatch.setattr('planerka.bot.отправка.отправить_с_кнопками',
                        lambda t, c, text, rows: кнопки.append(rows[0][0][1]))
    takt_a({'модель': 'test', 'источники': [], 'площадки': []}, root,
           Path('planerka/blocks'), date(2026, 10, 12),
           зов=lambda *a, **k: '## Банк тем\n- [ ] A\n', пересобрать=True)
    assert отправить_банк_тем('test', '1', root)['отправлено'] == ['A']
    assert кнопки[0] != старая
    assert отправить_банк_тем('test', '1', root)['отправлено'] == []
