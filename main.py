import os
from aiogram import Bot, Dispatcher, executor, types

# Берём токен из переменной окружения
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

if not TELEGRAM_BOT_TOKEN:
    raise RuntimeError("Нужно задать TELEGRAM_BOT_TOKEN в переменных окружения")

bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher(bot)

# Простейшее состояние: кто сейчас должен ввести инфоповод
waiting_infopovod = set()


@dp.message_handler(commands=["start"])
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    waiting_infopovod.add(user_id)

    text = (
        "Привет! Давай сделаем новый пост для Константина.\n\n"
        "Введите инфоповод.\n"
        "Что произошло? Где? С кем?\n"
        "Если инфоповода нет — напишите «нет»."
    )
    await message.answer(text)


@dp.message_handler()
async def handle_any_message(message: types.Message):
    user_id = message.from_user.id

    # Обрабатываем только тех, кто после /start
    if user_id not in waiting_infopovod:
        # На этом шаге игнорируем всё лишнее
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

    # На этом шаге просто показываем, как мы его поняли
    await message.answer(resp)

    # Снимаем пользователя с ожидания инфоповода
    waiting_infopovod.discard(user_id)


if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
