import os
import asyncio
from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove,
)
from aiogram.filters import CommandStart

# --- ДОСТУП К БОТУ ---

ALLOWED_USERNAMES = {"dkokhel", "kochelme"}  # только ты


def is_allowed(message: Message) -> bool:
    username = (message.from_user.username or "").lower()
    return username in ALLOWED_USERNAMES


# --- СОСТОЯНИЯ ---

waiting_infopovod = set()
waiting_topic_choice = set()
waiting_topic_custom = set()
waiting_release_type = set()
waiting_photo_or_create = set()

# Данные по пользователю
user_infopovod = {}
user_topic = {}
user_link = {}
user_release_type = {}
user_photo: dict[int, list[str]] = {}  # список file_id, максимум 3

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


def create_post_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Создать пост")],
        ],
        resize_keyboard=True,
    )


def extract_link(text: str) -> str | None:
    for part in text.split():
        if part.startswith("http://") or part.startswith("https://"):
            return part
    return None


async def go_to_photo_step(user_id: int, message: Message):
    waiting_photo_or_create.add(user_id)
    user_photo[user_id] = []

    text = (
        "Теперь можете отправить фото для поста.\n"
        "Можно прикрепить не более 3 фотографий.\n"
        "Если фото не нужно — просто нажмите «Создать пост»."
    )
    await message.answer(text, reply_markup=create_post_keyboard())


# ----- /start -----


@dp.message(CommandStart())
async def cmd_start(message: Message):
    if not is_allowed(message):
        await message.answer("Доступ к этому боту ограничен.")
        return

    user_id = message.from_user.id

    # Сбрасываем все состояния и данные
    waiting_infopovod.discard(user_id)
    waiting_topic_choice.discard(user_id)
    waiting_topic_custom.discard(user_id)
    waiting_release_type.discard(user_id)
    waiting_photo_or_create.discard(user_id)

    user_infopovod.pop(user_id, None)
    user_topic.pop(user_id, None)
    user_link.pop(user_id, None)
    user_release_type.pop(user_id, None)
    user_photo.pop(user_id, None)

    waiting_infopovod.add(user_id)

    text = (
        "Привет! Давай сделаем новый пост для Константина.\n\n"
        "Введите инфоповод.\n"
        "Что произошло? Где? С кем?\n"
        "Если инфоповода нет — нажмите кнопку «Без инфоповода»."
    )
    await message.answer(text, reply_markup=infopovod_keyboard())


# ----- ФОТО -----


@dp.message(F.photo)
async def handle_photo(message: Message):
    if not is_allowed(message):
        await message.answer("Доступ к этому боту ограничен.")
        return

    user_id = message.from_user.id

    if user_id not in waiting_photo_or_create:
        return

    # Берём список фоток пользователя, если нет — создаём
    photos = user_photo.get(user_id)
    if photos is None:
        photos = []
        user_photo[user_id] = photos

    # Добавляем новое фото
    file_id = message.photo[-1].file_id
    photos.append(file_id)

    # Жёсткий лимит: не более 3
    if len(photos) > 3:
        # Откатываем лишнее фото
        photos.pop()

        await message.answer(
            "Можно прикрепить не более 3 фотографий.\n"
            "Лишние кадры я не сохраняю.\n"
            "Когда будете готовы — нажмите «Создать пост».",
            reply_markup=create_post_keyboard(),
        )
        return

    await message.answer(
        f"Фото {len(photos)}/3 принято.\n"
        "Если хотите добавить ещё — отправьте новое фото.\n"
        "Когда будете готовы — нажмите «Создать пост».",
        reply_markup=create_post_keyboard(),
    )

# ----- ТЕКСТОВЫЕ СООБЩЕНИЯ -----


@dp.message()
async def handle_any_message(message: Message):
    if not is_allowed(message):
        await message.answer("Доступ к этому боту ограничен.")
        return

    user_id = message.from_user.id
    raw = (message.text or "").strip()
    low = raw.lower()

    # 1) Инфоповод
    if user_id in waiting_infopovod:
        if raw == "Без инфоповода" or low == "нет" or raw == "":
            # Инфоповода нет -> идём в выбор темы
            waiting_infopovod.discard(user_id)
            waiting_topic_choice.add(user_id)

            user_infopovod[user_id] = None

            text = (
                "Инфоповода нет.\n"
                "Выберите тему поста или введите свою:"
            )
            await message.answer(text, reply_markup=topic_keyboard())
            return

        # Инфоповод есть
        link = extract_link(raw)

        if link:
            # Убираем ссылку из текста
            parts = [
                p for p in raw.split()
                if not (p.startswith("http://") or p.startswith("https://"))
            ]
            text_without_link = " ".join(parts).strip()

            if text_without_link:
                infopovod_text = text_without_link
            else:
                infopovod_text = "Продвижение по ссылке"

            user_infopovod[user_id] = infopovod_text
            user_link[user_id] = link

            waiting_infopovod.discard(user_id)
            waiting_release_type.add(user_id)

            text = (
                "Принял инфоповод и увидел ссылку.\n\n"
                f"Инфоповод:\n«{infopovod_text}»\n\n"
                f"Ссылка: {link}\n\n"
                "Это премьера?"
            )
            await message.answer(text, reply_markup=release_type_keyboard())
        else:
            # Инфоповод без ссылки -> сразу к фото (Тема не нужна)
            user_infopovod[user_id] = raw
            user_link[user_id] = None
            user_release_type[user_id] = None
            waiting_infopovod.discard(user_id)

            await message.answer(
                "Принял инфоповод.\n"
                "Тема не требуется, переходим к фото.",
                reply_markup=ReplyKeyboardRemove(),
            )
            await go_to_photo_step(user_id, message)

        return

    # 2) Тип релиза (если была ссылка)
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

        await message.answer(
            "Принял тип релиза. Переходим к фото.",
            reply_markup=ReplyKeyboardRemove(),
        )
        await go_to_photo_step(user_id, message)
        return

    # 3) Выбор темы (ветка без инфоповода)
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

            await message.answer(
                f"Принял тему: «{topic}».\nПереходим к фото.",
                reply_markup=ReplyKeyboardRemove(),
            )
            await go_to_photo_step(user_id, message)
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

    # 4) Ручной ввод темы (ветка без инфоповода)
    if user_id in waiting_topic_custom:
        topic = raw
        waiting_topic_custom.discard(user_id)
        user_topic[user_id] = topic

        await message.answer(
            f"Принял тему: «{topic}».\nПереходим к фото.",
            reply_markup=ReplyKeyboardRemove(),
        )
        await go_to_photo_step(user_id, message)
        return

    # 5) Фото / Создать пост
    if user_id in waiting_photo_or_create:
        if raw == "Создать пост":
            waiting_photo_or_create.discard(user_id)

            infopovod = user_infopovod.get(user_id)
            topic = user_topic.get(user_id)
            link = user_link.get(user_id)
            rtype = user_release_type.get(user_id)
            photos = user_photo.get(user_id) or []
            photo_info = f"есть ({len(photos)} шт.)" if photos else "нет"

            # Здесь пока заглушка — позже вместо этого будет вызов агента-писателя
            text = (
                "Данные для генерации поста собраны.\n\n"
                f"Инфоповод: {infopovod or 'нет'}\n"
                f"Тема: {topic or 'нет'}\n"
                f"Ссылка: {link or 'нет'}\n"
                f"Тип релиза: {rtype or 'нет'}\n"
                f"Фото: {photo_info}.\n\n"
                "На этом шаге дальше будет вызываться агент-писатель Константина."
            )
            await message.answer(text, reply_markup=ReplyKeyboardRemove())

            # Чистим данные
            user_infopovod.pop(user_id, None)
            user_topic.pop(user_id, None)
            user_link.pop(user_id, None)
            user_release_type.pop(user_id, None)
            user_photo.pop(user_id, None)

            return

        await message.answer(
            "Если хотите добавить фото — отправьте его (не более 3 штук).\n"
            "Когда будете готовы — нажмите «Создать пост».",
            reply_markup=create_post_keyboard(),
        )
        return

    # Вне сценария — молчим
    return


async def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("Нужно задать TELEGRAM_BOT_TOKEN в переменных окружения")

    bot = Bot(token=token)
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == "__main__":
    asyncio.run(main())
