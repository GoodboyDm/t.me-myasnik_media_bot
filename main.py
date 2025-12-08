import os
import asyncio
from aiogram import Bot, Dispatcher
from aiogram.types import Message
from aiogram.filters import CommandStart

# Храним id пользователей, от которых ждём инфоповод
waiting_infopovod = set()

dp = Dispatcher()


@dp.message(CommandStart())
async def cmd_start(message: Message):
    user_id = message.from_user.id
    waiting_infopovod.add(user_id)

    text = (
        "Привет! Давай сделаем новый пост для Константина.\n\n"
        "Введите инфоповод.\n"
        "Что произошло? Где? С кем?\n"
        "Если инфоповода нет — напишите «нет»."
    )
    await message.answer(text)


@dp.message()
async def handle_any_message(message: Message):
    user_id = message.from_user.id

    # Обрабатываем только тех, кто после /start
    if user_id not in waiting_infopovod:
        return

    raw = (message.text or "").strip()
    low = raw.lower()

    if low == "нет" or raw == "":
        infopovod = "нет"
        resp = "Инфоповод: НЕТ.\nПозже здесь будем спрашивать тему и фото."
    else:
        infopovod = raw
        resp = (
            "Принял инфоповод.\n\n"
            f"Текст инфоповода:\n«{infopovod}»\n\n"
            "На следующем шаге сюда прикрутим тему, ссылку и фото."
        )

    await message.answer(resp)
    waiting_infopovod.discard(user_id)


async def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("Нужно задать TELEGRAM_BOT_TOKEN в переменных окружения")

    bot = Bot(token=token)
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == "__main__":
    asyncio.run(main())
