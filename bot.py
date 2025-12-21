import asyncio
import logging
import os
import re
from contextlib import asynccontextmanager

# Работа с БД
import asyncpg
# Переменные окружения
import dotenv
# Сервер и API
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Бот
from aiogram import Bot, Dispatcher, F, types
from aiogram.enums import ChatMemberStatus
from aiogram.filters import Command
from aiogram.types import (
    BotCommand, 
    BufferedInputFile, 
    InlineKeyboardButton, 
    InlineKeyboardMarkup, 
    InputMediaPhoto, 
    MessageReactionUpdated, 
    WebAppInfo
)

# Импорт вашей рисовалки
# Файл main_draw.py должен лежать рядом
from main_draw import create_active_user_image, create_top_sticker_image, create_top_words_image

# --- КОНФИГУРАЦИЯ ---
dotenv.load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")
# URL вашего React приложения (без слэша в конце)
WEB_APP_URL = "https://chatly1-iota.vercel.app" 

if not BOT_TOKEN or not DATABASE_URL:
    raise ValueError("Пожалуйста, укажите BOT_TOKEN и DATABASE_URL в файле .env")

logging.basicConfig(level=logging.INFO)

# Инициализация объектов
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
db_pool = None

# Список стоп-слов
STOP_WORDS = {
    "и", "в", "не", "на", "я", "что", "с", "а", "то", "как", "у", "все", "но", "по", 
    "он", "она", "так", "же", "от", "о", "ты", "за", "да", "из", "к", "мы", "бы", "вы", 
    "ну", "ли", "ни", "много", "это", "есть", "для", "тебе", "меня"
}

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---

def clean_and_split_text(text):
    """Очищает текст от знаков и разбивает на слова"""
    if not text: return []
    # Оставляем только буквы и пробелы, приводим к нижнему регистру
    text = re.sub(r'[^\w\s]', '', text.lower())
    return [w for w in text.split() if len(w) > 2 and w not in STOP_WORDS]

async def init_db_pool():
    """Создание пула соединений и таблиц"""
    global db_pool
    db_pool = await asyncpg.create_pool(dsn=DATABASE_URL)
    async with db_pool.acquire() as connection:
        # Таблица стикеров
        await connection.execute('''
            CREATE TABLE IF NOT EXISTS sticker_stats (
                chat_id BIGINT, 
                unique_id TEXT, 
                file_id TEXT, 
                count INTEGER DEFAULT 1, 
                PRIMARY KEY (chat_id, unique_id)
            )
        ''')
        # Таблица слов
        await connection.execute('''
            CREATE TABLE IF NOT EXISTS word_stats (
                chat_id BIGINT, 
                word TEXT, 
                count INTEGER DEFAULT 1, 
                PRIMARY KEY (chat_id, word)
            )
        ''')
        # Таблица пользователей
        await connection.execute('''
            CREATE TABLE IF NOT EXISTS user_stats (
                chat_id BIGINT, 
                user_id BIGINT, 
                full_name TEXT, 
                msg_count INTEGER DEFAULT 1, 
                PRIMARY KEY (chat_id, user_id)
            )
        ''')
        # Таблица сообщений (для реакций и истории)
        await connection.execute('''
            CREATE TABLE IF NOT EXISTS message_stats (
                chat_id BIGINT, 
                message_id BIGINT, 
                user_id BIGINT, 
                full_name TEXT, 
                content TEXT, 
                length INTEGER, 
                reaction_count INTEGER DEFAULT 0, 
                PRIMARY KEY (chat_id, message_id)
            )
        ''')
    print("✅ База данных подключена и таблицы проверены.")

async def delete_chat_data(chat_id):
    """Удаление всех данных чата (если бота кикнули)"""
    if not db_pool: return
    async with db_pool.acquire() as connection:
        await connection.execute('DELETE FROM sticker_stats WHERE chat_id = $1', chat_id)
        await connection.execute('DELETE FROM word_stats WHERE chat_id = $1', chat_id)
        await connection.execute('DELETE FROM user_stats WHERE chat_id = $1', chat_id)
        await connection.execute('DELETE FROM message_stats WHERE chat_id = $1', chat_id)

async def generate_and_send_stats_images(chat_id: int):
    """
    Основная функция генерации картинок.
    Вызывается ТОЛЬКО когда React просит об этом через API.
    """
    if not db_pool: return False

    # Переменные для данных
    user_name = "Никто"
    user_id = None
    msg_count = 0
    avatar_bytes = None
    top_words = [] 
    sticker_file_id = None
    sticker_count = 0
    sticker_bytes = None

    # 1. Сбор данных из БД
    async with db_pool.acquire() as conn:
        # Самый активный юзер
        user_row = await conn.fetchrow(
            'SELECT user_id, full_name, msg_count FROM user_stats WHERE chat_id=$1 ORDER BY msg_count DESC LIMIT 1', 
            chat_id
        )
        if user_row:
            user_name = user_row['full_name']
            msg_count = user_row['msg_count']
            user_id = user_row['user_id']
        
        # Топ слов
        words_rows = await conn.fetch(
            'SELECT word, count FROM word_stats WHERE chat_id=$1 ORDER BY count DESC LIMIT 3', 
            chat_id
        )
        top_words = [(r['word'], r['count']) for r in words_rows]

        # Топ стикер
        sticker_row = await conn.fetchrow(
            'SELECT file_id, count FROM sticker_stats WHERE chat_id=$1 ORDER BY count DESC LIMIT 1', 
            chat_id
        )
        if sticker_row:
            sticker_file_id = sticker_row['file_id']
            sticker_count = sticker_row['count']

    # 2. Скачивание аватарки (если есть юзер)
    if user_id:
        try:
            photos = await bot.get_user_profile_photos(user_id)
            if photos.total_count > 0:
                # Берем самое лучшее качество (последний элемент в массиве photos[0])
                file_id = photos.photos[0][-1].file_id 
                file_info = await bot.get_file(file_id)
                downloaded_file = await bot.download_file(file_info.file_path)
                avatar_bytes = downloaded_file.read()
        except Exception as e:
            print(f"Ошибка загрузки аватара: {e}")

    # 3. Скачивание стикера
    if sticker_file_id:
        try:
            st_file_info = await bot.get_file(sticker_file_id)
            st_downloaded = await bot.download_file(st_file_info.file_path)
            sticker_bytes = st_downloaded.read()
        except Exception: 
            pass

    # 4. Генерация картинок (в потоках, чтобы не блокировать сервер)
    media_group = []
    
    # -- Картинка 1: Активный юзер
    if msg_count > 0:
        image_active = await asyncio.to_thread(create_active_user_image, avatar_bytes, msg_count, user_name)
        if image_active:
            file_active = BufferedInputFile(image_active.read(), filename="active.png")
            media_group.append(InputMediaPhoto(media=file_active, caption="#ChatlyStats"))

    # -- Картинка 2: Слова
    if top_words:
        image_words = await asyncio.to_thread(create_top_words_image, top_words)
        if image_words:
            file_words = BufferedInputFile(image_words.read(), filename="words.png")
            media_group.append(InputMediaPhoto(media=file_words))

    # -- Картинка 3: Стикер
    if sticker_bytes:
        image_sticker = await asyncio.to_thread(create_top_sticker_image, sticker_bytes, sticker_count)
        if image_sticker:
            file_sticker = BufferedInputFile(image_sticker.read(), filename="sticker.png")
            media_group.append(InputMediaPhoto(media=file_sticker))

    # 5. Отправка в чат
    if media_group:
        try:
            await bot.send_media_group(chat_id=chat_id, media=media_group)
            return True
        except Exception as e:
            print(f"Ошибка отправки альбома: {e}")
            return False
    
    return False

# --- LIFESPAN (ЗАПУСК/ОСТАНОВКА) ---

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Старт
    await init_db_pool()
    await bot.set_my_commands([BotCommand(command="stats", description="Открыть статистику")])
    await bot.delete_webhook(drop_pending_updates=True)
    
    # Запускаем поллинг бота в фоне
    polling_task = asyncio.create_task(
        dp.start_polling(
            bot, 
            allowed_updates=["message", "message_reaction", "chat_member", "my_chat_member"]
        )
    )
    print("🚀 Сервер запущен, бот слушает обновления...")
    
    yield # Работа приложения
    
    # Остановка
    polling_task.cancel()
    if db_pool:
        await db_pool.close()
    print("👋 Сервер остановлен.")

# --- FASTAPI ПРИЛОЖЕНИЕ ---
app = FastAPI(lifespan=lifespan)

# CORS (разрешаем запросы с вашего сайта)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # В продакшене лучше указать конкретный домен
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- API ЭНДПОИНТЫ ---

@app.get("/api/chat/{chat_id}")
async def get_chat_stats_api(chat_id: int):
    """Отдает JSON данные для React приложения"""
    if not db_pool:
        return {"error": "База данных не подключена"}

    async with db_pool.acquire() as conn:
        # Активный юзер
        user_row = await conn.fetchrow(
            'SELECT user_id, full_name, msg_count FROM user_stats WHERE chat_id=$1 ORDER BY msg_count DESC LIMIT 1', 
            chat_id
        )
        
        active_user_data = None
        if user_row:
            # Получаем URL аватарки для фронтенда
            avatar_url = None
            try:
                photos = await bot.get_user_profile_photos(user_row['user_id'])
                if photos.total_count > 0:
                    # Берем маленькую картинку для иконки (photos[0][0])
                    file_id = photos.photos[0][0].file_id 
                    file_info = await bot.get_file(file_id)
                    # Формируем ссылку через Telegram API
                    avatar_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_info.file_path}"
            except Exception:
                pass

            active_user_data = {
                "name": user_row['full_name'],
                "count": user_row['msg_count'],
                "avatar_url": avatar_url
            }

        # Топ слов (берем топ 10 для сайта, даже если на картинке 3)
        words_rows = await conn.fetch(
            'SELECT word, count FROM word_stats WHERE chat_id=$1 ORDER BY count DESC LIMIT 10', 
            chat_id
        )
        top_words = [{"word": r['word'], "count": r['count']} for r in words_rows]

    return {
        "chat_id": chat_id,
        "active_user": active_user_data,
        "top_words": top_words
    }

@app.post("/api/share/{chat_id}")
async def share_stats_endpoint(chat_id: int):
    """
    Эндпоинт, который вызывает React при нажатии кнопки 'Поделиться'.
    Запускает генерацию и отправку картинок в чат.
    """
    try:
        success = await generate_and_send_stats_images(chat_id)
        if success:
            return {"status": "success", "message": "Images sent to chat"}
        else:
            return {"status": "no_data", "message": "No stats available or error"}
    except Exception as e:
        return {"status": "error", "details": str(e)}

# --- ХЕНДЛЕРЫ БОТА (AIOGRAM) ---

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer("Привет! Я собираю статистику чата. Напиши /stats, чтобы увидеть итоги.")

@dp.message(Command("stats"))
async def cmd_stats(message: types.Message):
    """
    Теперь эта команда отправляет ТОЛЬКО кнопку для открытия Mini App.
    """
    chat_id = message.chat.id
    
    # Формируем ссылку с параметром id
    app_url = f"{WEB_APP_URL}/?id={chat_id}"
    
    # Кнопка WebApp
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📱 Открыть статистику", web_app=WebAppInfo(url=app_url))]
    ])
    
    await message.answer(
        text=(
            "<b>📊 Статистика чата готова!</b>\n\n"
            "Нажми кнопку ниже, чтобы посмотреть анимированный отчет.\n"
            "Внутри приложения можно нажать <b>«Поделиться»</b>, чтобы отправить картинки в этот чат."
        ),
        reply_markup=keyboard,
        parse_mode="HTML"
    )

@dp.my_chat_member()
async def on_bot_status_change(event: types.ChatMemberUpdated):
    """Если бота удалили из чата - чистим БД"""
    if event.new_chat_member.status in (ChatMemberStatus.LEFT, ChatMemberStatus.KICKED):
        await delete_chat_data(event.chat.id)

@dp.message(F.sticker)
async def count_stickers(message: types.Message):
    """Учет стикеров"""
    if not db_pool: return
    async with db_pool.acquire() as conn:
        await conn.execute('''
            INSERT INTO sticker_stats (chat_id, unique_id, file_id, count) VALUES ($1, $2, $3, 1)
            ON CONFLICT (chat_id, unique_id) DO UPDATE SET count = sticker_stats.count + 1, file_id = EXCLUDED.file_id
        ''', message.chat.id, message.sticker.file_unique_id, message.sticker.file_id)

@dp.message_reaction()
async def track_reactions(event: MessageReactionUpdated):
    """Учет реакций"""
    if not db_pool: return
    chat_id = event.chat.id
    message_id = event.message_id
    # Считаем общее кол-во реакций на сообщении
    count = len(event.new_reaction)
    async with db_pool.acquire() as conn:
        await conn.execute(
            'UPDATE message_stats SET reaction_count = $1 WHERE chat_id = $2 AND message_id = $3', 
            count, chat_id, message_id
        )

@dp.message(F.text)
async def process_text_message(message: types.Message):
    """Учет текстовых сообщений, пользователей и слов"""
    # Игнорируем команды
    if message.text.startswith("/"): return
    if not db_pool: return
    
    chat_id = message.chat.id
    user_id = message.from_user.id
    name = message.from_user.full_name
    text = message.text

    async with db_pool.acquire() as conn:
        # 1. Обновляем статистику пользователя
        await conn.execute('''
            INSERT INTO user_stats (chat_id, user_id, full_name, msg_count) VALUES ($1, $2, $3, 1)
            ON CONFLICT (chat_id, user_id) DO UPDATE SET msg_count = user_stats.msg_count + 1, full_name = EXCLUDED.full_name
        ''', chat_id, user_id, name)
        
        # 2. Сохраняем сообщение (для длины и реакций)
        await conn.execute(
            'INSERT INTO message_stats (chat_id, message_id, user_id, full_name, content, length, reaction_count) VALUES ($1, $2, $3, $4, $5, $6, 0)', 
            chat_id, message.message_id, user_id, name, text, len(text)
        )
        
        # 3. Разбиваем на слова и считаем их
        words = clean_and_split_text(text)
        for word in words:
            await conn.execute('''
                INSERT INTO word_stats (chat_id, word, count) VALUES ($1, $2, 1)
                ON CONFLICT (chat_id, word) DO UPDATE SET count = word_stats.count + 1
            ''', chat_id, word)

if __name__ == "__main__":
    # Запуск сервера
    uvicorn.run(app, host="0.0.0.0", port=8000)