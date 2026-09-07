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

ТОКЕН = "111111:ВЫДУМАННЫЙ-ТОКЕН-НЕ-НАСТОЯЩИЙ"


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


def test_отправить_с_кнопками_happy():
    with patch("planerka.bot.api.urlopen") as urlopen:
        urlopen.return_value = _успешный_ответ({"ok": True, "result": {"message_id": 2}})
        результат = отправить_с_кнопками(
            ТОКЕН, 123, "выбирайте", [("Да", "yes"), ("Нет", "no")]
        )

    assert результат == {"message_id": 2}
    запрос, _ = urlopen.call_args
    отправленный = json.loads(запрос[0].data)
    assert отправленный["reply_markup"]["inline_keyboard"] == [
        [{"text": "Да", "callback_data": "yes"}],
        [{"text": "Нет", "callback_data": "no"}],
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


def test_проверить_токен_happy():
    with patch("planerka.bot.api.urlopen") as urlopen:
        urlopen.return_value = _успешный_ответ(
            {"ok": True, "result": {"id": 1, "is_bot": True, "first_name": "Планёрка"}}
        )
        имя = проверить_токен(ТОКЕН)

    assert имя == "Планёрка"


# --- edge --------------------------------------------------------------


def test_ответить_на_нажатие_без_текста_не_отправляет_поле_text():
    with patch("planerka.bot.api.urlopen") as urlopen:
        urlopen.return_value = _успешный_ответ({"ok": True, "result": True})
        ответить_на_нажатие(ТОКЕН, "callback-2")

    запрос, _ = urlopen.call_args
    отправленный = json.loads(запрос[0].data)
    assert отправленный == {"callback_query_id": "callback-2"}


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


def test_отправить_с_кнопками_пустой_список_не_падает():
    with patch("planerka.bot.api.urlopen") as urlopen:
        urlopen.return_value = _успешный_ответ({"ok": True, "result": {"message_id": 3}})
        результат = отправить_с_кнопками(ТОКЕН, 123, "текст", [])

    assert результат == {"message_id": 3}
    запрос, _ = urlopen.call_args
    отправленный = json.loads(запрос[0].data)
    assert отправленный["reply_markup"]["inline_keyboard"] == []


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
