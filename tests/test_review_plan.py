from datetime import date
from pathlib import Path

import pytest

from planerka.runner.takt_b import takt_b


@pytest.fixture
def мир(tmp_path):
    (tmp_path / 'недели').mkdir()
    путь = tmp_path / 'недели/неделя – 2026-10-19.md'
    путь.write_text('## Банк тем\n- [x] A\n- [ ] B\n')
    return tmp_path, путь


@pytest.mark.parametrize('новый', [
    '## Банк тем\n- [ ] A\n- [x] B\n',
    '## Банк тем\n- [x] A\n- [x] B\n',
    '## Банк тем\n- [ ] A\n- [ ] B\n',
])
def test_3_изменённый_выбор_не_получает_старый_план(мир, новый):
    root, путь = мир
    def модель(*args, **kwargs):
        путь.write_text(новый)
        return '## Неделя по дням\nПлан A\n'
    with pytest.raises(RuntimeError, match='измен'):
        takt_b({'модель': 'test', 'источники': [], 'площадки': []}, root,
               Path('planerka/blocks'), date(2026, 10, 21), зов=модель)
    assert путь.read_text() == новый


def test_3_неизменённый_выбор_и_повторный_вызов(мир):
    root, путь = мир
    for _ in range(2):
        takt_b({'модель': 'test', 'источники': [], 'площадки': []}, root,
               Path('planerka/blocks'), date(2026, 10, 21),
               зов=lambda *a, **k: '## Неделя по дням\nПлан A\n')
    assert путь.read_text().count('## Неделя по дням') == 1


def test_3_таймаут_не_меняет_файл(мир):
    root, путь = мир
    прежде = путь.read_bytes()
    def модель(*args, **kwargs):
        raise TimeoutError('timeout')
    with pytest.raises(TimeoutError):
        takt_b({'модель': 'test', 'источники': [], 'площадки': []}, root,
               Path('planerka/blocks'), date(2026, 10, 21), зов=модель)
    assert путь.read_bytes() == прежде
