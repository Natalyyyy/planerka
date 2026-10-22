import fcntl
import os
from datetime import date
from pathlib import Path

import pytest

from planerka.bot.приём import принять_нажатие
from planerka.bot.темы import идентификатор
from planerka.runner.takt_a import takt_a
from planerka.runner.takt_b import takt_b


@pytest.mark.parametrize('писатель', ['кнопка', 'темы', 'план'])
def test_1_проверка_и_запись_под_общей_блокировкой(tmp_path, monkeypatch, писатель):
    (tmp_path / 'недели').mkdir()
    путь = tmp_path / 'недели/неделя – 2026-10-19.md'
    путь.write_text('## Банк тем\n- [x] A\n- [ ] B\n')
    monkeypatch.setattr('planerka.bot.приём.ответить_на_нажатие', lambda *a, **k: None)
    заменить = os.replace
    проверено = []
    def запись(src, dst):
        if Path(dst) == путь:
            with путь.with_name(путь.name + '.lock').open('a') as lock:
                try:
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    проверено.append(True)
                else:
                    fcntl.flock(lock, fcntl.LOCK_UN)
                    pytest.fail('Файл заменяется без общей блокировки проверки и записи')
        return заменить(src, dst)
    monkeypatch.setattr(os, 'replace', запись)
    config = {'модель': 'test', 'источники': [], 'площадки': []}
    if писатель == 'кнопка':
        принять_нажатие('test', '1', идентификатор('B') + ':b', tmp_path)
    elif писатель == 'темы':
        takt_a(config, tmp_path, Path('planerka/blocks'), date(2026, 10, 21),
               зов=lambda *a, **k: '## Банк тем\n- [ ] C\n', пересобрать=True)
    else:
        takt_b(config, tmp_path, Path('planerka/blocks'), date(2026, 10, 21),
               зов=lambda *a, **k: '## Неделя по дням\nA\n')
    assert проверено == [True]


def test_1_ошибка_освобождает_блокировку(tmp_path):
    from planerka.runner.файлы import блокировка_файла
    путь = tmp_path / 'week.md'
    with pytest.raises(OSError):
        with блокировка_файла(путь):
            raise OSError('disk full')
    for _ in range(2):
        with блокировка_файла(путь):
            assert путь.with_name(путь.name + '.lock').exists()


def test_1_два_писателя_не_теряют_разные_решения(tmp_path, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    (tmp_path / 'недели').mkdir()
    путь = tmp_path / 'недели/неделя – 2026-10-19.md'
    путь.write_text('## Банк тем\n- [ ] A\n- [ ] B\n')
    monkeypatch.setattr('planerka.bot.приём.ответить_на_нажатие', lambda *a, **k: None)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(принять_нажатие, 'test', тема,
                               идентификатор(тема) + ':b', tmp_path) for тема in ('A', 'B')]
        assert [f.result()['статус'] for f in futures] == ['записано', 'записано']
    assert путь.read_text() == '## Банк тем\n- [x] A\n- [x] B\n'
