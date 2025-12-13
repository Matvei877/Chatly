import asyncio
import logging
import asyncpg

from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.enums import ChatMemberStatus
from aiogram.types import BotCommand
import dotenv
import os

# --- НАСТРОЙКИ ---
dotenv.load_dotenv() # Загружаем настройки из файла .env

BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Глобальный пул соединений
db_pool = None

# --- БАЗА ДАННЫХ ---

async def init_db():
    global db_pool
    db_pool = await asyncpg.create_pool(dsn=DATABASE_URL)
    
    async with db_pool.acquire() as connection:
        await connection.execute('''
            CREATE TABLE IF NOT EXISTS sticker_stats (
                chat_id BIGINT,
                unique_id TEXT,
                file_id TEXT,
                count INTEGER DEFAULT 1,
                PRIMARY KEY (chat_id, unique_id)
            )
        ''')
        print("✅ База данных подключена!")

async def add_sticker_to_db(chat_id, unique_id, file_id):
    async with db_pool.acquire() as connection:
        await connection.execute('''
            INSERT INTO sticker_stats (chat_id, unique_id, file_id, count)
            VALUES ($1, $2, $3, 1)
            ON CONFLICT (chat_id, unique_id) DO UPDATE SET
                count = sticker_stats.count + 1,
                file_id = EXCLUDED.file_id
        ''', chat_id, unique_id, file_id)

async def get_top_sticker(chat_id):
    async with db_pool.acquire() as connection:
        row = await connection.fetchrow('''
            SELECT file_id, count FROM sticker_stats
            WHERE chat_id = $1
            ORDER BY count DESC
            LIMIT 1
        ''', chat_id)
        return row

async def delete_chat_data(chat_id):
    """Функция удаления данных чата"""
    async with db_pool.acquire() as connection:
        await connection.execute('DELETE FROM sticker_stats WHERE chat_id = $1', chat_id)
        print(f"INFO: Данные для чата {chat_id} были удалены (бота кикнули).")

# --- ХЕНДЛЕРЫ ---

# 1. Если бота удалили или кикнули (Срабатывает автоматически)
@dp.my_chat_member(F.new_chat_member.status.in_([
    ChatMemberStatus.LEFT,
    ChatMemberStatus.KICKED
]))
async def on_bot_removed(event: types.ChatMemberUpdated):
    """
    Срабатывает, когда бота удаляют из чата или банят.
    """
    chat_id = event.chat.id
    # Вызываем функцию очистки базы
    await delete_chat_data(chat_id)

# 2. Если бота добавили
@dp.message(F.new_chat_members)
async def on_join(message: types.Message):
    bot_obj = await bot.get_me()
    for member in message.new_chat_members:
        if member.id == bot_obj.id:
            await message.answer("Всем привет я Chatly! Сделайте меня админом, чтобы я проводил еженедельную статистику вашего общения!")
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer("Я - open-source project, который смотря сообщения вашего чата проводит статистику!")

@dp.message(F.sticker)
async def count_stickers(message: types.Message):
    await add_sticker_to_db(
        chat_id=message.chat.id,
        unique_id=message.sticker.file_unique_id,
        file_id=message.sticker.file_id
    )

@dp.message(Command("stats"))
async def send_top_sticker(message: types.Message):
    chat_id = message.chat.id
    bot_obj = await bot.get_me()
    
    try:
        member = await bot.get_chat_member(chat_id, bot_obj.id)
        if member.status not in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR]:
             await message.answer("❌ Сделайте меня админом.")
             return
    except Exception:
        pass

    row = await get_top_sticker(chat_id)
    if not row:
        await message.answer("Статистики пока нет.")
        return

    await message.answer_sticker(sticker=row['file_id'])
    await message.answer(f"🏆 Самый популярный стикер! ({row['count']} раз).")

async def main():
    await init_db()
    
    await bot.set_my_commands([
        BotCommand(command="stats", description="🏆 Статистика"),
        BotCommand(command="start", description="🏁 Информация")
    ])
    
    await bot.delete_webhook(drop_pending_updates=True)
    try:
        await dp.start_polling(bot)
    finally:
        await db_pool.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Бот выключен")