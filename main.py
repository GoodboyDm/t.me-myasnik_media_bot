import os
import asyncio
from pathlib import Path

from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove,
)
from aiogram.filters import CommandStart
from openai import OpenAI

# --- ДОСТУП К БОТУ ---

ALLOWED_USERNAMES = {"dkokhel", "kochelme"}  # ты и сестра


def is_allowed(message: Message) -> bool:
    username = (message.from_user.username or "").lower()
    return username in ALLOWED_USERNAMES


# --- ЗАГРУЗКА ПРОМПТА ИЗ ФАЙЛА ---

PROMPT_PATH = Path(__file__).parent / "myasnik_prompt.txt"
try:
    WRITER_SYSTEM_PROMPT = PROMPT_PATH.read_text(encoding="utf-8")
except FileNotFoundError:
    WRITER_SYSTEM_PROMPT = "ERROR: myasnik_prompt.txt not found"


# --- СОСТОЯНИЯ ---

waiting_infopovod = set()
waiting_topic_choice = set()
waiting_topic_custom = set()
waiting_release_type = set()
waiting_photo_or_create = set()

# Данные по пользователю
user_infopovod: dict[int, str | None] = {}
user_topic: dict[int, str | None] = {}
user_link: dict[int, str | None] = {}
user_release_type: dict[int, str | None] = {}
user_photo: dict[int, list[str]] = {}  # user_id -> list[file_id]

dp = Dispatcher()


# --- КЛАВИАТУРЫ ---

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


# --- ВЫЗОВ ПИСАТЕЛЯ ---


async def generate_post_with_writer(
    infopovod: str | None,
    topic: str | None,
    link: str | None,
    release_type: str | None,
    photos_count: int,
) -> str:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return (
            "Не удалось сгенерировать пост: не задан API-ключ.\n"
            "Нужно указать переменную окружения OPENAI_API_KEY в Railway."
        )

    client = OpenAI(api_key=api_key)

    photo_flag = "есть" if photos_count > 0 else "нет"

    user_prompt = f"""
Входные параметры для генерации поста:

ИНФОПОВОД: {infopovod or 'нет'}
ССЫЛКА: {link or 'нет'}
ТИП РЕЛИЗА: {release_type or 'нет'}
ТЕМА: {topic or 'нет'}
ФОТО: {photo_flag}

Сгенерируй пост строго по инструкциям из SYSTEM, соблюдай формат OUTPUT FORMAT.
"""

    try:
        response = await asyncio.to_thread(
            client.chat.completions.create,
            model="gpt-5-mini",
            messages=[
                {"role": "system", "content": WRITER_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.6,
        )
        content = response.choices[0].message.content or ""
        return content.strip()
    except Exception as e:
        text = str(e)
        if "insufficient_quota" in text or "You exceeded your current quota" in text:
            return (
                "Не удалось сгенерировать пост: закончился лимит API OpenAI.\n\n"
                "Нужно пополнить баланс в кабинете OpenAI Platform и "
                "после этого попробовать ещё раз."
            )
        return (
            "Не удалось сгенерировать пост из-за технической ошибки.\n"
            "Попробуй ещё раз чуть позже."
        )


# ----- /start -----


@dp.message(CommandStart())
async def cmd_start(message: Message):
    if not is_allowed(message):
        await message.answer("Доступ к этому боту ограничен.")
        return

    user_id = message.from_user.id

    # Сбрасываем состояния и данные
    for s in (
        waiting_infopovod,
        waiting_topic_choice,
        waiting_topic_custom,
        waiting_release_type,
        waiting_photo_or_create,
    ):
        s.discard(user_id)

    for d in (
        user_infopovod,
        user_topic,
        user_link,
        user_release_type,
        user_photo,
    ):
        d.pop(user_id, None)

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

    photos = user_photo.get(user_id)
    if photos is None:
        photos = []
        user_photo[user_id] = photos

    # Уже есть 3 фото → новое не сохраняем
    if len(photos) >= 3:
        await message.answer(
            "Можно прикрепить не более 3 фотографий.\n"
            "Новое фото я не сохраняю.\n"
            "Когда будете готовы — нажмите «Создать пост».",
            reply_markup=create_post_keyboard(),
        )
        return

    file_id = message.photo[-1].file_id
    photos.append(file_id)

    if len(photos) < 3:
        await message.answer(
            f"Фото {len(photos)}/3 принято.\n"
            "Если хотите добавить ещё — отправьте новое фото.\n"
            "Когда будете готовы — нажмите «Создать пост».",
            reply_markup=create_post_keyboard(),
        )
    else:
        await message.answer(
            "Фото 3/3 принято.\n"
            "Лимит достигнут, новые фото я не буду сохранять.\n"
            "Можете сразу нажать «Создать пост».",
            reply_markup=create_post_keyboard(),
        )


# ----- ТЕКСТ -----


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
            waiting_infopovod.discard(user_id)
            waiting_topic_choice.add(user_id)
            user_infopovod[user_id] = None

            text = (
                "Инфоповода нет.\n"
                "Выберите тему поста или введите свою:"
            )
            await message.answer(text, reply_markup=topic_keyboard())
            return

        link = extract_link(raw)
        if link:
            # убираем ссылку из текста инфоповода
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

    # 4) Ручной ввод темы
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
            photos_count = len(photos)

            post_output = await generate_post_with_writer(
                infopovod=infopovod,
                topic=topic,
                link=link,
                release_type=rtype,
                photos_count=photos_count,
            )

            await message.answer(post_output, reply_markup=ReplyKeyboardRemove())

            # Чистим данные
            for d in (
                user_infopovod,
                user_topic,
                user_link,
                user_release_type,
                user_photo,
            ):
                d.pop(user_id, None)

            return

        await message.answer(
            "Если хотите добавить фото — отправьте его (не более 3 штук).\n"
            "Когда будете готовы — нажмите «Создать пост».",
            reply_markup=create_post_keyboard(),
        )
        return

    # Вне сценария — ничего не делаем
    return


async def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("Нужно задать TELEGRAM_BOT_TOKEN в переменных окружения")

    bot = Bot(token=token)
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == "__main__":
    asyncio.run(main())
