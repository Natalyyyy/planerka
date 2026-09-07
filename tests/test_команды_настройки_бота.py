"""Подкоманды `run.py`, которыми интервью настройки проверяет бота.

Блок 2 скилла `planerka-setup` должен уметь при человеке проверить токен и
узнать chat_id из первого сообщения. Раньше он диктовал для этого инлайновый
`python3 -c '...'` со своим, упрощённым разбором `.env` — вторая копия того,
что уже умеет `run.py::_прочесть_env_файл`. В этом проекте такие копии уже
дважды расходились (атомарная запись жила в трёх экземплярах, идентификатор
темы считался двумя способами), и разойдутся ровно тогда, когда в настоящем
разборе появится то, чего нет в упрощённом: кавычки вокруг значения, пробелы,
комментарий строкой. Поэтому обе операции — подкоманды `run.py`, и разбор
`.env` у них ровно один.

Сеть замокана всюду: подменяются `проверить_токен` и `получить_обновления`,
которые `run.py` держит у себя по имени. Наружу прогон не ходит.

Домашний каталог не трогается ни одним тестом: `УКАЗАТЕЛЬ` подменяется во
временную папку автофикстурой. Настоящий `~/.planerka/папка.txt` — рабочий
файл человека, и однажды он уже был затёрт живой пробой.
"""
import json

import pytest

from planerka import run
from planerka.bot.api import ОшибкаСети, ОшибкаТокена

ТОКЕН = "111111:VYDUMANNYJ-TOKEN-NE-NASTOYASHCHIJ"


@pytest.fixture(autouse=True)
def указатель_во_временной_папке(tmp_path, monkeypatch):
    monkeypatch.setattr(run, "УКАЗАТЕЛЬ", tmp_path / "дом" / ".planerka" / "папка.txt")


@pytest.fixture
def заметки(tmp_path):
    папка = tmp_path / "заметки"
    папка.mkdir()
    return папка


def _env(папка, содержимое: str) -> None:
    (папка / ".env").write_text(содержимое, encoding="utf-8")


def _запомнить_токен(куда: dict, имя_бота: str = "@planerka_bot"):
    """Подделка `проверить_токен`, которая запоминает, с чем её позвали."""
    def проверка(токен):
        куда["токен"] = токен
        return имя_бота
    return проверка


# --- проверить-бота


def test_проверить_бота_называет_имя_бота_с_собачкой(заметки, monkeypatch, capsys):
    _env(заметки, f"TELEGRAM_BOT_TOKEN={ТОКЕН}\n")
    отдано = {}
    monkeypatch.setattr(run, "проверить_токен", _запомнить_токен(отдано))
    run.main(["проверить-бота", "--папка", str(заметки)])
    вывод = capsys.readouterr().out
    assert "@planerka_bot" in вывод, f"имя бота человеку не показано: {вывод!r}"
    assert отдано["токен"] == ТОКЕН, "проверялся не тот токен, что лежит в .env"


def test_проверить_бота_берёт_токен_из_env_файла_а_не_из_окружения(заметки, monkeypatch, capsys):
    """Тот же приоритет, что у команды «бот»: в шелле человека может годами
    жить токен другого бота от другой задачи."""
    _env(заметки, "TELEGRAM_BOT_TOKEN=111111:IZ-ENV-FAJLA\n")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "222222:IZ-OKRUZHENIYA")
    отдано = {}
    monkeypatch.setattr(run, "проверить_токен", _запомнить_токен(отдано))
    run.main(["проверить-бота", "--папка", str(заметки)])
    assert отдано["токен"] == "111111:IZ-ENV-FAJLA"


def test_проверить_бота_читает_env_настоящим_разбором_а_не_упрощённым(заметки, monkeypatch):
    """Кавычки вокруг значения, комментарий строкой, пробелы вокруг `=` — всё
    это умеет `_прочесть_env_файл`. Если подкоманда заведёт свой разбор, он
    почти наверняка не будет уметь чего-то из этого — и токен молча приедет
    вместе с кавычками."""
    _env(заметки, '# токен планёрки\n\nTELEGRAM_BOT_TOKEN = "111111:V-KAVYCHKAH"\n')
    отдано = {}
    monkeypatch.setattr(run, "проверить_токен", _запомнить_токен(отдано))
    run.main(["проверить-бота", "--папка", str(заметки)])
    assert отдано["токен"] == "111111:V-KAVYCHKAH", "разбор .env разошёлся с run.py"


def test_проверить_бота_без_токена_говорит_что_положить_и_куда(заметки, capsys):
    with pytest.raises(SystemExit) as выход:
        run.main(["проверить-бота", "--папка", str(заметки)])
    assert выход.value.code == 1
    ошибка = capsys.readouterr().err
    assert "TELEGRAM_BOT_TOKEN" in ошибка, ошибка
    assert ".env" in ошибка, ошибка


def test_проверить_бота_отдаёт_ошибку_телеграма_строкой_а_не_трейсбеком(заметки, monkeypatch, capsys):
    _env(заметки, f"TELEGRAM_BOT_TOKEN={ТОКЕН}\n")

    def падает(_):
        raise ОшибкаТокена("Телеграм не принял токен — проверьте, что скопировали его целиком")

    monkeypatch.setattr(run, "проверить_токен", падает)
    with pytest.raises(SystemExit) as выход:
        run.main(["проверить-бота", "--папка", str(заметки)])
    assert выход.value.code == 1
    ошибка = capsys.readouterr().err
    assert "не принял токен" in ошибка, ошибка
    assert "Traceback" not in ошибка


def test_проверить_бота_не_печатает_сам_токен(заметки, monkeypatch, capsys):
    """Токен — секрет: у кого он есть, тот и есть бот. Для подтверждения
    человеку хватает имени с собачкой."""
    _env(заметки, f"TELEGRAM_BOT_TOKEN={ТОКЕН}\n")
    monkeypatch.setattr(run, "проверить_токен", lambda _: "@planerka_bot")
    run.main(["проверить-бота", "--папка", str(заметки)])
    напечатано = capsys.readouterr()
    assert ТОКЕН not in напечатано.out and ТОКЕН not in напечатано.err


def test_проверить_бота_работает_без_конфига(заметки, monkeypatch, capsys):
    """Интервью зовёт команду в блоке 2, а `конфиг.json` появляется только в
    самом конце интервью. Требование конфига сделало бы команду бесполезной
    ровно там, где она нужна."""
    assert not (заметки / "конфиг.json").exists()
    _env(заметки, f"TELEGRAM_BOT_TOKEN={ТОКЕН}\n")
    monkeypatch.setattr(run, "проверить_токен", lambda _: "@planerka_bot")
    run.main(["проверить-бота", "--папка", str(заметки)])
    assert "@planerka_bot" in capsys.readouterr().out


def test_проверить_бота_не_трогает_указатель_в_домашнем_каталоге(заметки, monkeypatch, capsys):
    _env(заметки, f"TELEGRAM_BOT_TOKEN={ТОКЕН}\n")
    monkeypatch.setattr(run, "проверить_токен", lambda _: "@planerka_bot")
    run.main(["проверить-бота", "--папка", str(заметки)])
    assert not run.УКАЗАТЕЛЬ.exists(), (
        "диагностическая команда переписала указатель на папку заметок — "
        "у человека может быть вторая папка, и молча переключать его нельзя")


def test_проверить_бота_на_несуществующей_папке_говорит_понятно(tmp_path, capsys):
    with pytest.raises(SystemExit) as выход:
        run.main(["проверить-бота", "--папка", str(tmp_path / "нет-такой")])
    assert выход.value.code == 1
    assert "не найдена" in capsys.readouterr().err.lower()


# --- узнать-chat-id


def _обновление(chat_id, имя="Ирина", ключ="message"):
    return {"update_id": 1, ключ: {"chat": {"id": chat_id, "first_name": имя}}}


def test_узнать_chat_id_печатает_готовую_строку_для_env(заметки, monkeypatch, capsys):
    _env(заметки, f"TELEGRAM_BOT_TOKEN={ТОКЕН}\n")
    monkeypatch.setattr(run, "получить_обновления", lambda *а, **к: [_обновление(123456789)])
    run.main(["узнать-chat-id", "--папка", str(заметки)])
    вывод = capsys.readouterr().out
    assert "TELEGRAM_CHAT_ID=123456789" in вывод, f"строку для .env не показали: {вывод!r}"
    assert "Ирина" in вывод, "человеку не сказали, чей это диалог"


def test_узнать_chat_id_без_сообщений_не_падает(заметки, monkeypatch, capsys):
    """«Сообщений нет» — не ошибка: сообщение могло не успеть дойти. Код
    выхода нулевой, чтобы интервью спокойно позвало команду ещё раз."""
    _env(заметки, f"TELEGRAM_BOT_TOKEN={ТОКЕН}\n")
    monkeypatch.setattr(run, "получить_обновления", lambda *а, **к: [])
    run.main(["узнать-chat-id", "--папка", str(заметки)])
    вывод = capsys.readouterr().out
    assert "пока нет" in вывод, вывод


def test_узнать_chat_id_показывает_все_чаты_без_дублей(заметки, monkeypatch, capsys):
    _env(заметки, f"TELEGRAM_BOT_TOKEN={ТОКЕН}\n")
    monkeypatch.setattr(run, "получить_обновления", lambda *а, **к: [
        _обновление(111, "Ирина"), _обновление(111, "Ирина"), _обновление(222, "Рабочий чат"),
    ])
    run.main(["узнать-chat-id", "--папка", str(заметки)])
    вывод = capsys.readouterr().out
    assert вывод.count("TELEGRAM_CHAT_ID=111") == 1, f"дубль чата: {вывод!r}"
    assert "TELEGRAM_CHAT_ID=222" in вывод, "второй чат потерян — выбирать должен человек"


def test_узнать_chat_id_видит_отредактированное_сообщение(заметки, monkeypatch, capsys):
    _env(заметки, f"TELEGRAM_BOT_TOKEN={ТОКЕН}\n")
    monkeypatch.setattr(run, "получить_обновления",
                        lambda *а, **к: [_обновление(777, ключ="edited_message")])
    run.main(["узнать-chat-id", "--папка", str(заметки)])
    assert "TELEGRAM_CHAT_ID=777" in capsys.readouterr().out


def test_узнать_chat_id_не_падает_на_обновлении_без_сообщения(заметки, monkeypatch, capsys):
    _env(заметки, f"TELEGRAM_BOT_TOKEN={ТОКЕН}\n")
    monkeypatch.setattr(run, "получить_обновления", lambda *а, **к: [
        {"update_id": 1, "callback_query": {"data": "b:abc"}},
        {"update_id": 2},
        _обновление(555),
    ])
    run.main(["узнать-chat-id", "--папка", str(заметки)])
    assert "TELEGRAM_CHAT_ID=555" in capsys.readouterr().out


def test_узнать_chat_id_ждёт_сообщение_конечное_время(заметки, monkeypatch, capsys):
    """Опрос без таймаута повесил бы интервью на живом человеке."""
    отдано = {}

    def опрос(токен, **к):
        отдано.update(к)
        return []

    _env(заметки, f"TELEGRAM_BOT_TOKEN={ТОКЕН}\n")
    monkeypatch.setattr(run, "получить_обновления", опрос)
    run.main(["узнать-chat-id", "--папка", str(заметки)])
    assert isinstance(отдано.get("таймаут"), int) and отдано["таймаут"] > 0, отдано


def test_узнать_chat_id_отдаёт_сетевую_ошибку_строкой(заметки, monkeypatch, capsys):
    _env(заметки, f"TELEGRAM_BOT_TOKEN={ТОКЕН}\n")

    def падает(*а, **к):
        raise ОшибкаСети("Телеграм не отвечает — проверьте связь")

    monkeypatch.setattr(run, "получить_обновления", падает)
    with pytest.raises(SystemExit) as выход:
        run.main(["узнать-chat-id", "--папка", str(заметки)])
    assert выход.value.code == 1
    ошибка = capsys.readouterr().err
    assert "не отвечает" in ошибка and "Traceback" not in ошибка


def test_узнать_chat_id_без_токена_не_ходит_в_сеть(заметки, monkeypatch, capsys):
    def нельзя(*а, **к):
        raise AssertionError("пошли в сеть без токена")

    monkeypatch.setattr(run, "получить_обновления", нельзя)
    with pytest.raises(SystemExit) as выход:
        run.main(["узнать-chat-id", "--папка", str(заметки)])
    assert выход.value.code == 1
    assert "TELEGRAM_BOT_TOKEN" in capsys.readouterr().err


# --- обе команды в одном ряду с остальными


def test_команды_настройки_объявлены_в_списке_команд():
    for команда in ("проверить-бота", "узнать-chat-id"):
        assert команда in run.КОМАНДЫ, f"{команда} не объявлена в CLI"


def test_флаги_чужих_команд_к_настроечным_не_лепятся(заметки, capsys):
    for команда, флаг in (("проверить-бота", "--пересобрать"),
                          ("узнать-chat-id", "--обойти-блокировку")):
        with pytest.raises(SystemExit) as выход:
            run.main([команда, флаг, "--папка", str(заметки)])
        assert выход.value.code == 1, команда
        capsys.readouterr()


def test_настроечные_команды_не_ломают_прежние(заметки, monkeypatch, capsys):
    """Такты «темы» и «план» по-прежнему требуют конфиг — новые команды не
    должны были размыть эту проверку на всех."""
    (заметки / "конфиг.json").write_text(json.dumps({"модель": "m"}), encoding="utf-8")
    with pytest.raises(SystemExit):
        run.main(["план", "--папка", str(заметки / "нет-такой")])
    capsys.readouterr()
