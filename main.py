import os
import asyncio
from aiogram import Bot, Dispatcher
from aiogram.types import (
    Message,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove,
)
from aiogram.filters import CommandStart

# Простые "состояния" по пользователям
waiting_infopovod = set()
waiting_topic_choice = set()
waiting_topic_custom = set()

dp = Dispatcher()


def infopovod_keyboard() -> ReplyKeyboardMarkup:
    # aiogram 3: нужно явно задать keyboard=[ [...], [...] ]
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Без инфоповода")],
        ],
        resize_keyboard=True,
    )


def topic_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Путь мужчины и сила")],
            [KeyboardButton(text="Семья и дети")],
            [KeyboardButton(text="Активность и спорт")],
            [KeyboardButton(text="Город, дорога и музыка")],
            [KeyboardButton(text="Ввести свою тему")],
        ],
        resize_keyboard=True,
    )


@dp.message(CommandStart())
async def cmd_start(message: Message):
    user_id = message.from_user.id

    # Сбрасываем все состояния
    waiting_infopovod.discard(user_id)
    waiting_topic_choice.discard(user_id)
    waiting_topic_custom.discard(user_id)

    waiting_infopovod.add(user_id)

    text = (
        "Привет! Давай сделаем новый пост для Константина.\n\n"
        "Введите инфоповод.\n"
        "Что произошло? Где? С кем?\n"
        "Если инфоповода нет — нажмите кнопку «Без инфоповода»."
    )
    await message.answer(text, reply_markup=infopovod_keyboard())


@dp.message()
async def handle_any_message(message: Message):
    user_id = message.from_user.id
    raw = (message.text or "").strip()
    low = raw.lower()

    # 1) Шаг инфоповода
    if user_id in waiting_infopovod:
        # Ветвь "без инфоповода" — через кнопку или слово "нет"
        if raw == "Без инфоповода" or low == "нет" or raw == "":
            waiting_infopovod.discard(user_id)
            waiting_topic_choice.add(user_id)

            text = (
                "Инфоповода нет.\n"
                "Выберите тему поста или введите свою:"
            )
            await message.answer(text, reply_markup=topic_keyboard())
        else:
            # Есть осмысленный инфоповод
            waiting_infopovod.discard(user_id)

            resp = (
                "Принял инфоповод.\n\n"
                f"Текст инфоповода:\n«{raw}»\n\n"
                "На следующих шагах добавим ссылку, фото и генерацию поста."
            )
            await message.answer(resp, reply_markup=ReplyKeyboardRemove())

        return

    # 2) Шаг выбора темы по кнопкам
    if user_id in waiting_topic_choice:
        if raw in [
            "Путь мужчины и сила",
            "Семья и дети",
            "Активность и спорт",
            "Город, дорога и музыка",
        ]:
            topic = raw
            waiting_topic_choice.discard(user_id)

            resp = (
                f"Принял тему: «{topic}».\n\n"
                "Позже сюда добавим фото и генерацию поста."
            )
            await message.answer(resp, reply_markup=ReplyKeyboardRemove())
            return

        if raw == "Ввести свою тему" or low == "ввести свою тему":
            waiting_topic_choice.discard(user_id)
            waiting_topic_custom.add(user_id)

            await message.answer(
                "Введите тему поста одним сообщением.",
                reply_markup=ReplyKeyboardRemove(),
            )
            return

        await message.answer(
            "Пожалуйста, выберите тему на клавиатуре или нажмите «Ввести свою тему».",
            reply_markup=topic_keyboard(),
        )
        return

    # 3) Шаг ручного ввода темы
    if user_id in waiting_topic_custom:
        topic = raw
        waiting_topic_custom.discard(user_id)

        resp = (
            f"Принял тему: «{topic}».\n\n"
            "Позже на этом месте будет генерация текста поста."
        )
        await message.answer(resp, reply_markup=ReplyKeyboardRemove())
        return

    # Вне сценария — пока молчим
    return


async def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("Нужно задать TELEGRAM_BOT_TOKEN в переменных окружения")

    bot = Bot(token=token)
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == "__main__":
    asyncio.run(main())
