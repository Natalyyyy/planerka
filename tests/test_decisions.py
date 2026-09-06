from planerka.runner.decisions import parse_decisions

БАНК = """## Банк тем

- [x] Первая тема · откуда: встреча
- [?] Вторая тема · откуда: чат
- [-] Третья тема · откуда: заметка
- [ ] Четвёртая тема · откуда: архив

## Додумать

- Какой-то вопрос
"""


def test_разбирает_четыре_состояния():
    out = parse_decisions(БАНК)
    assert out["беру"] == ["Первая тема"]
    assert out["подумать"] == ["Вторая тема"]
    assert out["нет"] == ["Третья тема"]
    assert out["не_решено"] == ["Четвёртая тема"]


def test_откуда_отрезается():
    out = parse_decisions("- [x] Тема · откуда: файл")
    assert out["беру"] == ["Тема"]


def test_пустой_текст_даёт_пустые_списки():
    out = parse_decisions("")
    assert out == {"беру": [], "подумать": [], "нет": [], "не_решено": []}


def test_ни_одной_галочки_не_проставлено():
    out = parse_decisions("- [ ] Раз\n- [ ] Два")
    assert out["беру"] == [] and len(out["не_решено"]) == 2


def test_все_темы_отклонены():
    out = parse_decisions("- [-] Раз\n- [-] Два")
    assert out["беру"] == [] and len(out["нет"]) == 2


def test_дубль_темы_сохраняется_дважды():
    out = parse_decisions("- [x] Тема\n- [x] Тема")
    assert out["беру"] == ["Тема", "Тема"]


def test_строки_вне_банка_не_попадают():
    out = parse_decisions("просто текст\n## Додумать\n- Вопрос")
    assert all(v == [] for v in out.values())


def test_неизвестный_маркер_игнорируется():
    out = parse_decisions("- [z] Тема")
    assert all(v == [] for v in out.values())


def test_регистр_маркера_не_важен():
    out = parse_decisions("- [X] Тема")
    assert out["беру"] == ["Тема"]
