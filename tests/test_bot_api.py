"""Тесты клиента Telegram Bot API.

Токены — выдуманные строки, сеть везде замокана: прогон не должен
ходить наружу.
"""
import io
import json
import socket
from unittest.mock import MagicMock, patch

import pytest

from planerka.bot.api import (
    ОшибкаКонфликта,
    ОшибкаОтвета,
    ОшибкаСети,
    ОшибкаТелеграма,
    ОшибкаТокена,
    отправить_с_кнопками,
    отправить_сообщение,
    ответить_на_нажатие,
    получить_обновления,
    проверить_токен,
)
from urllib.error import HTTPError, URLError

# Токен выдуманный, но ЛАТИНИЦЕЙ: настоящие токены Телеграма — ASCII, и
# `_запрос` теперь отказывает не-ASCII токену до сетевого вызова (см.
# test_кириллица_в_токене_даёт_ошибку_токена_а_не_unicodeerror). Кириллица
# здесь сделала бы валидный по смыслу тест невалидным по входным данным.
ТОКЕН = "111111:VYDUMANNYJ-TOKEN-NE-NASTOYASHCHIJ"


def _успешный_ответ(тело: dict) -> MagicMock:
    контекст = MagicMock()
    контекст.__enter__.return_value.read.return_value = json.dumps(тело).encode("utf-8")
    контекст.__exit__.return_value = False
    return контекст


def _http_ошибка(код: int, тело: dict) -> HTTPError:
    данные = json.dumps(тело).encode("utf-8")
    return HTTPError(
        url="https://api.telegram.org/botX/x",
        code=код,
        msg="ошибка",
        hdrs=None,
        fp=io.BytesIO(данные),
    )


# --- happy path ------------------------------------------------------


def test_отправить_сообщение_happy():
    with patch("planerka.bot.api.urlopen") as urlopen:
        urlopen.return_value = _успешный_ответ({"ok": True, "result": {"message_id": 1}})
        результат = отправить_сообщение(ТОКЕН, 123, "привет")

    assert результат == {"message_id": 1}
    запрос, именованные = urlopen.call_args
    assert именованные["timeout"] == 10
    отправленный = json.loads(запрос[0].data)
    assert отправленный == {"chat_id": 123, "text": "привет"}
    assert запрос[0].full_url == f"https://api.telegram.org/bot{ТОКЕН}/sendMessage"


def test_отправить_с_кнопками_happy_несколько_рядов():
    # Раскладка явная: вызывающий сам решает форму (список рядов), клиент
    # не разбивает плоский список на строки самостоятельно.
    with patch("planerka.bot.api.urlopen") as urlopen:
        urlopen.return_value = _успешный_ответ({"ok": True, "result": {"message_id": 2}})
        результат = отправить_с_кнопками(
            ТОКЕН, 123, "выбирайте", [[("Да", "yes")], [("Нет", "no")]]
        )

    assert результат == {"message_id": 2}
    запрос, _ = urlopen.call_args
    отправленный = json.loads(запрос[0].data)
    assert отправленный["reply_markup"]["inline_keyboard"] == [
        [{"text": "Да", "callback_data": "yes"}],
        [{"text": "Нет", "callback_data": "no"}],
    ]


def test_отправить_с_кнопками_один_ряд_из_трёх_кнопок():
    # Сценарий «беру / подумать / нет» — один горизонтальный ряд,
    # с телефона одно движение, а не три промаха по столбику.
    with patch("planerka.bot.api.urlopen") as urlopen:
        urlopen.return_value = _успешный_ответ({"ok": True, "result": {"message_id": 4}})
        результат = отправить_с_кнопками(
            ТОКЕН, 123, "берёте тему?",
            [[("беру", "take"), ("подумать", "think"), ("нет", "no")]],
        )

    assert результат == {"message_id": 4}
    запрос, _ = urlopen.call_args
    отправленный = json.loads(запрос[0].data)
    assert отправленный["reply_markup"]["inline_keyboard"] == [
        [
            {"text": "беру", "callback_data": "take"},
            {"text": "подумать", "callback_data": "think"},
            {"text": "нет", "callback_data": "no"},
        ]
    ]


def test_ответить_на_нажатие_happy():
    with patch("planerka.bot.api.urlopen") as urlopen:
        urlopen.return_value = _успешный_ответ({"ok": True, "result": True})
        итог = ответить_на_нажатие(ТОКЕН, "callback-1", "принято")

    assert итог is None
    запрос, _ = urlopen.call_args
    отправленный = json.loads(запрос[0].data)
    assert отправленный == {"callback_query_id": "callback-1", "text": "принято"}


def test_получить_обновления_happy():
    with patch("planerka.bot.api.urlopen") as urlopen:
        urlopen.return_value = _успешный_ответ(
            {"ok": True, "result": [{"update_id": 1}, {"update_id": 2}]}
        )
        обновления = получить_обновления(ТОКЕН)

    assert обновления == [{"update_id": 1}, {"update_id": 2}]


def test_проверить_токен_happy_возвращает_username_с_собачкой():
    # @username — то, что человек видит в @BotFather и по чему узнаёт
    # бота однозначно; first_name он мог задать любым и не помнит.
    with patch("planerka.bot.api.urlopen") as urlopen:
        urlopen.return_value = _успешный_ответ(
            {
                "ok": True,
                "result": {
                    "id": 1, "is_bot": True,
                    "first_name": "Планёрка", "username": "planerka_bot",
                },
            }
        )
        имя = проверить_токен(ТОКЕН)

    assert имя == "@planerka_bot"


# --- edge --------------------------------------------------------------


def test_ответить_на_нажатие_без_текста_не_отправляет_поле_text():
    with patch("planerka.bot.api.urlopen") as urlopen:
        urlopen.return_value = _успешный_ответ({"ok": True, "result": True})
        ответить_на_нажатие(ТОКЕН, "callback-2")

    запрос, _ = urlopen.call_args
    отправленный = json.loads(запрос[0].data)
    assert отправленный == {"callback_query_id": "callback-2"}


def test_ответить_на_нажатие_show_alert_передаётся_телеграму():
    # Полоска-подсказка Телеграма гаснет за пару секунд — для отказов и
    # перезаписи прежнего решения этого мало, человек может её не увидеть.
    # show_alert=True просит Телеграм показать модальное окно, которое
    # не исчезает само.
    with patch("planerka.bot.api.urlopen") as urlopen:
        urlopen.return_value = _успешный_ответ({"ok": True, "result": True})
        ответить_на_нажатие(ТОКЕН, "callback-3", "внимание", show_alert=True)

    запрос, _ = urlopen.call_args
    отправленный = json.loads(запрос[0].data)
    assert отправленный == {
        "callback_query_id": "callback-3", "text": "внимание", "show_alert": True,
    }


def test_ответить_на_нажатие_без_show_alert_поле_не_отправляется():
    # По умолчанию — полоска, а не модальное окно; поле show_alert вообще
    # не должно попадать в запрос, если его не просили явно (иначе старые
    # вызовы без него незаметно поменяли бы поведение у Телеграма).
    with patch("planerka.bot.api.urlopen") as urlopen:
        urlopen.return_value = _успешный_ответ({"ok": True, "result": True})
        ответить_на_нажатие(ТОКЕН, "callback-4", "текст")

    запрос, _ = urlopen.call_args
    отправленный = json.loads(запрос[0].data)
    assert "show_alert" not in отправленный


def test_получить_обновления_пустой_список():
    with patch("planerka.bot.api.urlopen") as urlopen:
        urlopen.return_value = _успешный_ответ({"ok": True, "result": []})
        обновления = получить_обновления(ТОКЕН)

    assert обновления == []


def test_получить_обновления_без_callback_query_не_падает():
    with patch("planerka.bot.api.urlopen") as urlopen:
        urlopen.return_value = _успешный_ответ(
            {"ok": True, "result": [{"update_id": 5, "message": {"text": "привет"}}]}
        )
        обновления = получить_обновления(ТОКЕН)

    assert обновления == [{"update_id": 5, "message": {"text": "привет"}}]
    assert "callback_query" not in обновления[0]


def test_получить_обновления_передаёт_смещение_и_таймаут():
    with patch("planerka.bot.api.urlopen") as urlopen:
        urlopen.return_value = _успешный_ответ({"ok": True, "result": []})
        получить_обновления(ТОКЕН, смещение=42, таймаут=5)

    запрос, именованные = urlopen.call_args
    отправленный = json.loads(запрос[0].data)
    assert отправленный == {"timeout": 5, "offset": 42}
    assert именованные["timeout"] == 10  # 5 + запас на сетевой таймаут


def test_проверить_токен_без_username_возвращает_first_name_с_пометкой():
    # Отсутствие username не должно молча подсовывать first_name как
    # будто это и есть username — пометка обязана быть видна в строке.
    with patch("planerka.bot.api.urlopen") as urlopen:
        urlopen.return_value = _успешный_ответ(
            {"ok": True, "result": {"id": 1, "is_bot": True, "first_name": "Планёрка"}}
        )
        имя = проверить_токен(ТОКЕН)

    assert имя == "Планёрка (без @username)"
    assert not имя.startswith("@")


# --- error ---------------------------------------------------------------


def test_429_ждёт_retry_after_и_повторяет():
    with patch("planerka.bot.api.urlopen") as urlopen, \
            patch("planerka.bot.api.time.sleep") as сон:
        urlopen.side_effect = [
            _http_ошибка(429, {"ok": False, "parameters": {"retry_after": 3}}),
            _успешный_ответ({"ok": True, "result": {"message_id": 9}}),
        ]
        результат = отправить_сообщение(ТОКЕН, 123, "привет")

    assert результат == {"message_id": 9}
    сон.assert_called_once_with(3)
    assert urlopen.call_count == 2


def test_429_превышение_лимита_попыток_бросает_понятную_ошибку():
    with patch("planerka.bot.api.urlopen") as urlopen, \
            patch("planerka.bot.api.time.sleep"):
        urlopen.side_effect = _http_ошибка(429, {"ok": False, "parameters": {"retry_after": 1}})
        with pytest.raises(ОшибкаТелеграма) as исключение:
            отправить_сообщение(ТОКЕН, 123, "привет")

    assert "частот" in str(исключение.value)
    assert urlopen.call_count == 4  # разумный предел попыток, не бесконечно


def test_500_повтор_с_нарастающим_отступом():
    with patch("planerka.bot.api.urlopen") as urlopen, \
            patch("planerka.bot.api.time.sleep") as сон:
        urlopen.side_effect = [
            _http_ошибка(500, {"ok": False, "description": "внутренняя ошибка"}),
            _http_ошибка(502, {"ok": False, "description": "bad gateway"}),
            _успешный_ответ({"ok": True, "result": {"message_id": 10}}),
        ]
        результат = отправить_сообщение(ТОКЕН, 123, "привет")

    assert результат == {"message_id": 10}
    assert [вызов.args[0] for вызов in сон.call_args_list] == [1, 2]  # нарастающий отступ


def test_500_превышение_лимита_попыток_бросает_понятную_ошибку():
    with patch("planerka.bot.api.urlopen") as urlopen, \
            patch("planerka.bot.api.time.sleep"):
        urlopen.side_effect = _http_ошибка(503, {"ok": False, "description": "недоступен"})
        with pytest.raises(ОшибкаТелеграма) as исключение:
            отправить_сообщение(ТОКЕН, 123, "привет")

    assert "сервер" in str(исключение.value)
    assert urlopen.call_count == 4


def test_401_даёт_внятную_русскую_ошибку_а_не_трейсбек():
    with patch("planerka.bot.api.urlopen") as urlopen:
        urlopen.side_effect = _http_ошибка(
            401, {"ok": False, "error_code": 401, "description": "Unauthorized"}
        )
        with pytest.raises(ОшибкаТокена) as исключение:
            проверить_токен(ТОКЕН)

    сообщение = str(исключение.value)
    assert "401" not in сообщение
    assert "токен" in сообщение.lower()


def test_обрыв_связи_не_падает_молча():
    with patch("planerka.bot.api.urlopen") as urlopen:
        urlopen.side_effect = URLError("сеть недоступна")
        with pytest.raises(ОшибкаСети) as исключение:
            отправить_сообщение(ТОКЕН, 123, "привет")

    assert "интернет" in str(исключение.value).lower() or "связ" in str(исключение.value).lower()


def test_таймаут_сети_не_падает_молча():
    with patch("planerka.bot.api.urlopen") as urlopen:
        urlopen.side_effect = socket.timeout("timed out")
        with pytest.raises(ОшибкаСети):
            получить_обновления(ТОКЕН)


def test_ответ_не_json_даёт_понятную_ошибку():
    with patch("planerka.bot.api.urlopen") as urlopen:
        контекст = MagicMock()
        контекст.__enter__.return_value.read.return_value = "<html>не json</html>".encode("utf-8")
        контекст.__exit__.return_value = False
        urlopen.return_value = контекст
        with pytest.raises(ОшибкаОтвета):
            отправить_сообщение(ТОКЕН, 123, "привет")


def test_ответ_без_поля_ok_даёт_понятную_ошибку():
    with patch("planerka.bot.api.urlopen") as urlopen:
        urlopen.return_value = _успешный_ответ({"result": {"message_id": 1}})
        with pytest.raises(ОшибкаОтвета):
            отправить_сообщение(ТОКЕН, 123, "привет")


def test_ok_false_даёт_ошибку_с_описанием_телеграма():
    with patch("planerka.bot.api.urlopen") as urlopen:
        urlopen.return_value = _успешный_ответ(
            {"ok": False, "description": "chat not found"}
        )
        with pytest.raises(ОшибкаТелеграма) as исключение:
            отправить_сообщение(ТОКЕН, 123, "привет")

    assert "chat not found" in str(исключение.value)


def test_отправить_с_кнопками_пустой_список_рядов_даёт_понятную_ошибку():
    # Пустой список рядов — ошибка кода, вызвавшего функцию, а не
    # повод молча отправить сообщение без клавиатуры: HTTP-вызова быть
    # не должно вообще.
    with patch("planerka.bot.api.urlopen") as urlopen:
        with pytest.raises(ValueError) as исключение:
            отправить_с_кнопками(ТОКЕН, 123, "текст", [])

    urlopen.assert_not_called()
    assert "ряд" in str(исключение.value).lower()


# --- Important 1: потолок ожидания на 429 -------------------------------


def test_429_retry_after_в_пределах_потолка_ждёт_и_повторяет():
    # Дублирует ситуацию из test_429_ждёт_retry_after_и_повторяет, но
    # уже прицельно на границе с потолком — небольшой retry_after не
    # должен восприниматься как повод сразу бросить ошибку.
    with patch("planerka.bot.api.urlopen") as urlopen, \
            patch("planerka.bot.api.time.sleep") as сон:
        urlopen.side_effect = [
            _http_ошибка(429, {"ok": False, "parameters": {"retry_after": 10}}),
            _успешный_ответ({"ok": True, "result": {"message_id": 11}}),
        ]
        результат = отправить_сообщение(ТОКЕН, 123, "привет")

    assert результат == {"message_id": 11}
    сон.assert_called_once_with(10)


def test_429_retry_after_больше_потолка_не_спит_и_даёт_ошибку_с_числом_секунд():
    # Флуд-контроль Телеграма может попросить ждать сотни секунд — это
    # долгоживущий процесс, но блокировать вызывающего на минуты молча
    # нельзя: дедлайн вызова съедается незаметно.
    with patch("planerka.bot.api.urlopen") as urlopen, \
            patch("planerka.bot.api.time.sleep") as сон:
        urlopen.side_effect = _http_ошибка(
            429, {"ok": False, "parameters": {"retry_after": 300}}
        )
        with pytest.raises(ОшибкаТелеграма) as исключение:
            отправить_сообщение(ТОКЕН, 123, "привет")

    сон.assert_not_called()
    assert urlopen.call_count == 1  # даже не пытались повторить
    assert "300" in str(исключение.value)


# --- Important 2: описание Телеграма для прочих кодов --------------------


def test_400_chat_not_found_даёт_подсказку_написать_боту_первым():
    with patch("planerka.bot.api.urlopen") as urlopen:
        urlopen.side_effect = _http_ошибка(
            400, {"ok": False, "error_code": 400, "description": "Bad Request: chat not found"}
        )
        with pytest.raises(ОшибкаТелеграма) as исключение:
            отправить_сообщение(ТОКЕН, 123, "привет")

    сообщение = str(исключение.value)
    assert "chat not found" in сообщение
    assert "написал" in сообщение.lower()  # подсказка: написать боту первым
    assert "попробуйте позже" not in сообщение


def test_403_bot_blocked_даёт_подсказку_разблокировать():
    with patch("planerka.bot.api.urlopen") as urlopen:
        urlopen.side_effect = _http_ошибка(
            403,
            {"ok": False, "error_code": 403, "description": "Forbidden: bot was blocked by the user"},
        )
        with pytest.raises(ОшибкаТелеграма) as исключение:
            отправить_сообщение(ТОКЕН, 123, "привет")

    сообщение = str(исключение.value)
    assert "blocked by the user" in сообщение
    assert "разблокир" in сообщение.lower()
    assert "попробуйте позже" not in сообщение


def test_произвольный_4xx_с_описанием_показывает_описание_телеграма():
    with patch("planerka.bot.api.urlopen") as urlopen:
        urlopen.side_effect = _http_ошибка(
            409,
            {"ok": False, "error_code": 409, "description": "Conflict: terminated by other getUpdates request"},
        )
        with pytest.raises(ОшибкаТелеграма) as исключение:
            получить_обновления(ТОКЕН)

    assert "terminated by other getUpdates request" in str(исключение.value)


def test_409_даёт_ошибку_конфликта_а_не_обычную_телеграмную():
    """409 от getUpdates — почти всегда «этого бота уже опрашивает другой
    процесс» (двойной запуск), а не обычный временный сбой. Отдельный тип
    исключения даёт bot/процесс.py различить их и не говорить человеку
    «проблемы с интернетом», когда дело в двух запущенных процессах."""
    with patch("planerka.bot.api.urlopen") as urlopen:
        urlopen.side_effect = _http_ошибка(
            409,
            {"ok": False, "error_code": 409, "description": "Conflict: terminated by other getUpdates request"},
        )
        with pytest.raises(ОшибкаКонфликта) as исключение:
            получить_обновления(ТОКЕН)

    сообщение = str(исключение.value)
    assert "terminated by other getUpdates request" in сообщение
    assert "уже опрашивает" in сообщение.lower()
    assert isinstance(исключение.value, ОшибкаТелеграма)  # остаётся в семье ОшибкаБота


def test_409_без_описания_в_теле_не_падает():
    with patch("planerka.bot.api.urlopen") as urlopen:
        urlopen.side_effect = _http_ошибка(409, {"ok": False})
        with pytest.raises(ОшибкаКонфликта) as исключение:
            получить_обновления(ТОКЕН)
    assert "409" in str(исключение.value)


def test_4xx_без_описания_в_теле_не_падает_даёт_общий_текст():
    with patch("planerka.bot.api.urlopen") as urlopen:
        urlopen.side_effect = _http_ошибка(418, {"ok": False})
        with pytest.raises(ОшибкаТелеграма) as исключение:
            отправить_сообщение(ТОКЕН, 123, "привет")

    assert "418" in str(исключение.value)


def test_4xx_тело_ошибки_не_json_не_падает_с_трейсбеком():
    with patch("planerka.bot.api.urlopen") as urlopen:
        ошибка = HTTPError(
            url="https://api.telegram.org/botX/x", code=404, msg="Not Found",
            hdrs=None, fp=io.BytesIO("<html>не json</html>".encode("utf-8")),
        )
        urlopen.side_effect = ошибка
        with pytest.raises(ОшибкаТелеграма) as исключение:
            отправить_сообщение(ТОКЕН, 123, "привет")

    assert "404" in str(исключение.value)


# --- токен с посторонними символами: человеческая ошибка вместо UnicodeEncodeError
#
# Токен попадает прямо в URL. Любой не-ASCII символ в нём валит `urlopen`
# UnicodeEncodeError'ом из недр http.client — трейсбеком на первом же шаге
# знакомства с продуктом, посреди интервью настройки. А сценарий частый:
# при копировании из @BotFather цепляется невидимый знак, или человек
# набирает токен руками в русской раскладке и попадает в кириллические
# «с», «е», «о», «а», «р» — внешне строка выглядит правильной.

ТОКЕН_С_КИРИЛЛИЦЕЙ = "111111:AAxxYYzz-с-русской-буквой"
ТОКЕН_С_НЕВИДИМЫМ = "111111:AAxxYYzz​xxxx"


def test_кириллица_в_токене_даёт_ошибку_токена_а_не_unicodeerror():
    with patch("planerka.bot.api.urlopen") as урл:
        with pytest.raises(ОшибкаТокена) as поймано:
            проверить_токен(ТОКЕН_С_КИРИЛЛИЦЕЙ)
    assert урл.call_count == 0, "проверка формы токена обязана быть ДО сетевого вызова"
    текст = str(поймано.value)
    assert "посторонние символы" in текст, f"текст ошибки не объясняет, что не так: {текст!r}"
    assert "заново" in текст, f"текст ошибки не говорит, что делать: {текст!r}"


def test_невидимый_символ_в_токене_тоже_ловится():
    with patch("planerka.bot.api.urlopen") as урл:
        with pytest.raises(ОшибкаТокена):
            проверить_токен(ТОКЕН_С_НЕВИДИМЫМ)
    assert урл.call_count == 0


def test_получить_обновления_с_кириллицей_в_токене_тоже_не_падает_трейсбеком():
    """Проверка стоит на общем входе `_запрос`, а не только в `проверить_токен`:
    команда «узнать-chat-id» зовёт getUpdates, и до getMe там дела нет."""
    with patch("planerka.bot.api.urlopen") as урл:
        with pytest.raises(ОшибкаТокена):
            получить_обновления(ТОКЕН_С_КИРИЛЛИЦЕЙ)
    assert урл.call_count == 0


def test_отправка_сообщения_с_кириллицей_в_токене_тоже_ловится():
    with patch("planerka.bot.api.urlopen") as урл:
        with pytest.raises(ОшибкаТокена):
            отправить_сообщение(ТОКЕН_С_КИРИЛЛИЦЕЙ, 1, "привет")
    assert урл.call_count == 0


def test_кириллица_в_тексте_сообщения_не_запрещена():
    """Ограничение — про токен, а не про сообщения: банк тем русский целиком."""
    with patch("planerka.bot.api.urlopen", return_value=_успешный_ответ({"ok": True, "result": {}})):
        отправить_сообщение(ТОКЕН, 1, "Тема недели — про кассовый разрыв")


def test_обычный_ascii_токен_проверку_формы_проходит():
    with patch("planerka.bot.api.urlopen",
               return_value=_успешный_ответ({"ok": True, "result": {"username": "planerka_bot"}})):
        assert проверить_токен(ТОКЕН) == "@planerka_bot"
