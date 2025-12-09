import os
import re
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
waiting_release_type = set()

# Память по пользователю
user_infopovod = {}
user_topic = {}
user_link = {}
user_release_type = {}

dp = Dispatcher()


def infopovod_keyboard() -> ReplyKeyboardMarkup:
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


def release_type_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Да, премьера")],
            [KeyboardButton(text="Нет, уже вышло")],
        ],
        resize_keyboard=True,
    )


def extract_link(text: str) -> str | None:
    """Очень простой поиск ссылки: ищем http/https."""
    for part in text.split():
        if part.startswith("http://") or part.startswith("https://"):
            return part
    return None


@dp.message(CommandStart())
async def cmd_start(message: Message):
    user_id = message.from_user.id

    # Сбрасываем все состояния и данные
    waiting_infopovod.discard(user_id)
    waiting_topic_choice.discard(user_id)
    waiting_topic_custom.discard(user_id)
    waiting_release_type.discard(user_id)

    user_infopovod.pop(user_id, None)
    user_topic.pop(user_id, None)
    user_link.pop(user_id, None)
    user_release_type.pop(user_id, None)

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
        # Ветвь "без инфоповода" — кнопка или "нет"
        if raw == "Без инфоповода" or low == "нет" or raw == "":
            waiting_infopovod.discard(user_id)
            waiting_topic_choice.add(user_id)

            user_infopovod[user_id] = None

            text = (
                "Инфоповода нет.\n"
                "Выберите тему поста или введите свою:"
            )
            await message.answer(text, reply_markup=topic_keyboard())
            return

        # Есть инфоповод — проверяем, есть ли ссылка
        link = extract_link(raw)
        user_infopovod[user_id] = raw

        if link:
            user_link[user_id] = link
            waiting_infopovod.discard(user_id)
            waiting_release_type.add(user_id)

            text = (
                "Принял инфоповод и увидел ссылку.\n\n"
                f"Инфоповод:\n«{raw}»\n\n"
                f"Ссылка: {link}\n\n"
                "Это премьера?"
            )
            await message.answer(text, reply_markup=release_type_keyboard())
        else:
            # Инфоповод без ссылки — пока просто подтверждаем
            waiting_infopovod.discard(user_id)

            text = (
                "Принял инфоповод.\n\n"
                f"Текст инфоповода:\n«{raw}»\n\n"
                "На следующих шагах добавим тему (если нужно), ссылку, фото и генерацию поста."
            )
            await message.answer(text, reply_markup=ReplyKeyboardRemove())

        return

    # 2) Шаг выбора типа релиза (если была ссылка)
    if user_id in waiting_release_type:
        if raw == "Да, премьера":
            user_release_type[user_id] = "премьера"
        elif raw == "Нет, уже вышло":
            user_release_type[user_id] = "обычный релиз"
        else:
            await message.answer(
                "Пожалуйста, выберите один из вариантов:",
                reply_markup=release_type_keyboard(),
            )
            return

        waiting_release_type.discard(user_id)

        infopovod = user_infopovod.get(user_id)
        link = user_link.get(user_id)
        rtype = user_release_type.get(user_id)

        text = (
            "Принял данные для промо-композиции.\n\n"
            f"Инфоповод:\n«{infopovod}»\n\n"
            f"Ссылка: {link}\n"
            f"Тип релиза: {rtype}\n\n"
            "Дальше добавим шаг с фото и генерацией поста."
        )
        await message.answer(text, reply_markup=ReplyKeyboardRemove())
        return

    # 3) Шаг выбора темы по кнопкам (ветка без инфоповода)
    if user_id in waiting_topic_choice:
        if raw in [
            "Путь мужчины и сила",
            "Семья и дети",
            "Активность и спорт",
            "Город, дорога и музыка",
        ]:
            topic = raw
            waiting_topic_choice.discard(user_id)
            user_topic[user_id] = topic

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

    # 4) Шаг ручного ввода темы
    if user_id in waiting_topic_custom:
        topic = raw
        waiting_topic_custom.discard(user_id)
        user_topic[user_id] = topic

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
