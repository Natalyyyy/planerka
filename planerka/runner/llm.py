"""Единственное место, которое зовёт Claude CLI.

Модель передаётся всегда явно: дефолт CLI меняется и опорой быть не может.

Промпт уходит через stdin, а не аргументом командной строки: `collect`
собирает материал без ограничения объёма, и неделя транскриптов легко
перевешивает ARG_MAX — argv тут не выдержит.
"""
import subprocess


def run_claude(prompt: str, model: str, timeout_sec: int = 900) -> str:
    готово = subprocess.run(
        ["claude", "--model", model, "-p"],
        input=prompt,
        capture_output=True, text=True, timeout=timeout_sec,
    )
    if готово.returncode != 0:
        raise RuntimeError(f"claude вернул {готово.returncode}: {готово.stderr[:400]}")
    return готово.stdout
