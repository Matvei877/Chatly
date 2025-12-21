import asyncio
import logging
import asyncpg
import re
import os
import io
import dotenv
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.enums import ChatMemberStatus
from aiogram.types import BotCommand, MessageReactionUpdated, BufferedInputFile, InputMediaPhoto

# --- ИМПОРТ ---
from main_draw import create_active_user_image, create_top_words_image, create_top_sticker_image

# --- НАСТРОЙКИ ---
dotenv.load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")
logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
db_pool = None
STOP_WORDS = {"и", "в", "не", "на", "я", "что", "с", "а", "то", "как", "у", "все", "но", "по", "он", "она", "так", "же", "от", "о", "ты", "за", "да", "из", "к", "мы", "бы", "вы", "ну", "ли", "ни", "много", "это"}

# --- БД ---
async def init_db():
    global db_pool
    db_pool = await asyncpg.create_pool(dsn=DATABASE_URL)
    async with db_pool.acquire() as connection:
        await connection.execute('''CREATE TABLE IF NOT EXISTS sticker_stats (chat_id BIGINT, unique_id TEXT, file_id TEXT, count INTEGER DEFAULT 1, PRIMARY KEY (chat_id, unique_id))''')
        await connection.execute('''CREATE TABLE IF NOT EXISTS word_stats (chat_id BIGINT, word TEXT, count INTEGER DEFAULT 1, PRIMARY KEY (chat_id, word))''')
        await connection.execute('''CREATE TABLE IF NOT EXISTS user_stats (chat_id BIGINT, user_id BIGINT, full_name TEXT, msg_count INTEGER DEFAULT 1, PRIMARY KEY (chat_id, user_id))''')
        await connection.execute('''CREATE TABLE IF NOT EXISTS message_stats (chat_id BIGINT, message_id BIGINT, user_id BIGINT, full_name TEXT, content TEXT, length INTEGER, reaction_count INTEGER DEFAULT 0, PRIMARY KEY (chat_id, message_id))''')
        print("✅ База данных готова!")

async def delete_chat_data(chat_id):
    async with db_pool.acquire() as connection:
        await connection.execute('DELETE FROM sticker_stats WHERE chat_id = $1', chat_id)
        await connection.execute('DELETE FROM word_stats WHERE chat_id = $1', chat_id)
        await connection.execute('DELETE FROM user_stats WHERE chat_id = $1', chat_id)
        await connection.execute('DELETE FROM message_stats WHERE chat_id = $1', chat_id)

def clean_and_split_text(text):
    if not text: return []
    text = re.sub(r'[^\w\s]', '', text.lower())
    return [w for w in text.split() if len(w) > 2 and w not in STOP_WORDS]

# --- ХЕНДЛЕРЫ ---

@dp.message(Command("stats"))
async def send_stats(message: types.Message):
    chat_id = message.chat.id
    print(f"Запрос статистики из чата: {chat_id}")

    user_name = "Никто"
    user_id = None
    msg_count = 0
    avatar_bytes = None
    top_words = [] 
    
    sticker_file_id = None
    sticker_count = 0
    sticker_bytes = None

    # --- 1. СБОР ДАННЫХ ---
    async with db_pool.acquire() as conn:
        # Самый активный
        user_row = await conn.fetchrow('SELECT user_id, full_name, msg_count FROM user_stats WHERE chat_id=$1 ORDER BY msg_count DESC LIMIT 1', chat_id)
        if user_row:
            user_name = user_row['full_name']
            msg_count = user_row['msg_count']
            user_id = user_row['user_id']
        
        # Топ слова
        words_rows = await conn.fetch('SELECT word, count FROM word_stats WHERE chat_id=$1 ORDER BY count DESC LIMIT 3', chat_id)
        top_words = [(r['word'], r['count']) for r in words_rows]

        # Топ стикер
        sticker_row = await conn.fetchrow('SELECT file_id, count FROM sticker_stats WHERE chat_id=$1 ORDER BY count DESC LIMIT 1', chat_id)
        if sticker_row:
            sticker_file_id = sticker_row['file_id']
            sticker_count = sticker_row['count']

    # --- 2. СКАЧИВАНИЕ ФАЙЛОВ ---
    if user_id:
        try:
            photos = await bot.get_user_profile_photos(user_id)
            if photos.total_count > 0:
                file_id = photos.photos[0][-1].file_id 
                file_info = await bot.get_file(file_id)
                downloaded_file = await bot.download_file(file_info.file_path)
                avatar_bytes = downloaded_file.read()
        except Exception:
            pass
            
    if sticker_file_id:
        try:
            st_file_info = await bot.get_file(sticker_file_id)
            st_downloaded = await bot.download_file(st_file_info.file_path)
            sticker_bytes = st_downloaded.read()
        except Exception:
            pass

    # --- 3. ГЕНЕРАЦИЯ КАРТИНОК ---
    media_group = []

    # Картинка 1: Активный
    if msg_count > 0:
        image_active = await asyncio.to_thread(create_active_user_image, avatar_bytes, msg_count, user_name)
        if image_active:
            file_active = BufferedInputFile(image_active.read(), filename="active.png")
            media_group.append(InputMediaPhoto(media=file_active, caption="Статистика чата"))

    # Картинка 2: Слова
    if top_words:
        image_words = await asyncio.to_thread(create_top_words_image, top_words)
        if image_words:
            file_words = BufferedInputFile(image_words.read(), filename="words.png")
            media_group.append(InputMediaPhoto(media=file_words))

    # Картинка 3: Стикер
    if sticker_bytes:
        image_sticker = await asyncio.to_thread(create_top_sticker_image, sticker_bytes, sticker_count)
        if image_sticker:
            file_sticker = BufferedInputFile(image_sticker.read(), filename="sticker.png")
            media_group.append(InputMediaPhoto(media=file_sticker))

    # --- 4. ОТПРАВКА ---
    if media_group:
        await message.answer_media_group(media=media_group)
    else:
        await message.answer("❌ Недостаточно данных для статистики.")

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer("Я считаю статистику. Напиши /stats.")

@dp.my_chat_member()
async def on_bot_status_change(event: types.ChatMemberUpdated):
    if event.new_chat_member.status in (ChatMemberStatus.LEFT, ChatMemberStatus.KICKED):
        await delete_chat_data(event.chat.id)

@dp.message(F.sticker)
async def count_stickers(message: types.Message):
    async with db_pool.acquire() as conn:
        await conn.execute('''
            INSERT INTO sticker_stats (chat_id, unique_id, file_id, count) VALUES ($1, $2, $3, 1)
            ON CONFLICT (chat_id, unique_id) DO UPDATE SET count = sticker_stats.count + 1, file_id = EXCLUDED.file_id
        ''', message.chat.id, message.sticker.file_unique_id, message.sticker.file_id)

@dp.message_reaction()
async def track_reactions(event: MessageReactionUpdated):
    chat_id = event.chat.id
    message_id = event.message_id
    count = len(event.new_reaction)
    async with db_pool.acquire() as conn:
        await conn.execute('UPDATE message_stats SET reaction_count = $1 WHERE chat_id = $2 AND message_id = $3', count, chat_id, message_id)

@dp.message(F.text)
async def process_text_message(message: types.Message):
    if message.text.startswith("/"): return
    chat_id = message.chat.id
    user_id = message.from_user.id
    name = message.from_user.full_name
    text = message.text

    async with db_pool.acquire() as conn:
        await conn.execute('''
            INSERT INTO user_stats (chat_id, user_id, full_name, msg_count) VALUES ($1, $2, $3, 1)
            ON CONFLICT (chat_id, user_id) DO UPDATE SET msg_count = user_stats.msg_count + 1, full_name = EXCLUDED.full_name
        ''', chat_id, user_id, name)
        
        await conn.execute('INSERT INTO message_stats (chat_id, message_id, user_id, full_name, content, length, reaction_count) VALUES ($1, $2, $3, $4, $5, $6, 0)', 
                           chat_id, message.message_id, user_id, name, text, len(text))
        
        for word in clean_and_split_text(text):
            await conn.execute('''
                INSERT INTO word_stats (chat_id, word, count) VALUES ($1, $2, 1)
                ON CONFLICT (chat_id, word) DO UPDATE SET count = word_stats.count + 1
            ''', chat_id, word)

async def main():
    await init_db()
    await bot.set_my_commands([BotCommand(command="stats", description="Показать статистику")])
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot, allowed_updates=["message", "message_reaction", "chat_member", "my_chat_member"])

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Бот выключен")