import asyncio
import logging
import asyncpg
import re
import os
import dotenv
import asyncio
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.enums import ChatMemberStatus
from aiogram.types import BotCommand, MessageReactionUpdated

# --- НАСТРОЙКИ ---
dotenv.load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

# Включаем логирование, чтобы видеть ошибки в консоли
logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
db_pool = None

STOP_WORDS = {
    "и", "в", "во", "не", "что", "он", "на", "я", "с", "со", "как", "а", "то", "все", "она", "так", "его", "но", "да", "ты", "к", "у", "же", "вы", "за", "бы", "по", "только", "ее", "мне", "было", "вот", "от", "меня", "еще", "нет", "о", "из", "ему", "теперь", "когда", "даже", "ну", "вдруг", "ли", "если", "уже", "или", "ни", "быть", "был", "него", "до", "вас", "нибудь", "опять", "уж", "вам", "ведь", "там", "потом", "себя", "ничего", "ей", "может", "они", "тут", "где", "есть", "надо", "ней", "для", "мы", "тебя", "их", "чем", "была", "сам", "чтоб", "без", "будто", "чего", "раз", "тоже", "себе", "под", "будет", "ж", "тогда", "кто", "этот", "того", "потому", "этого", "какой", "совсем", "ним", "здесь", "этом", "один", "почти", "мой", "тем", "чтобы", "нее", "сейчас", "были", "куда", "зачем", "всех", "никогда", "можно", "при", "наконец", "два", "об", "другой", "хоть", "после", "над", "больше", "тот", "через", "эти", "нас", "про", "всего", "них", "какая", "много", "разве", "три", "эту", "моя", "впрочем", "хорошо", "свою", "этой", "перед", "иногда", "лучше", "чуть", "том", "нельзя", "такой", "им", "более", "всегда", "конечно", "всю", "между", "ок", "пон", "ладно", "спс", "привет"
}

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
        print(f"🗑 Данные чата {chat_id} очищены.")

def clean_and_split_text(text):
    if not text: return []
    text = re.sub(r'[^\w\s]', '', text.lower())
    return [w for w in text.split() if len(w) > 2 and w not in STOP_WORDS]

# --- ХЕНДЛЕРЫ (ПОРЯДОК ВАЖЕН!) ---

@dp.message(Command("stats"))
async def send_stats(message: types.Message):
    chat_id = message.chat.id
    print(f"Запрос статистики из чата: {chat_id}")

    async with db_pool.acquire() as conn:
        # 1. Топ стикер
        sticker = await conn.fetchrow('SELECT file_id, count FROM sticker_stats WHERE chat_id=$1 ORDER BY count DESC LIMIT 1', chat_id)
        
        # 2. Топ слово
        word = await conn.fetchrow('SELECT word, count FROM word_stats WHERE chat_id=$1 ORDER BY count DESC LIMIT 1', chat_id)
        
        # 3. Самый активный
        user = await conn.fetchrow('SELECT full_name, msg_count FROM user_stats WHERE chat_id=$1 ORDER BY msg_count DESC LIMIT 1', chat_id)
        
        # 4. Реакции
        reaction = await conn.fetchrow('SELECT full_name, content, reaction_count FROM message_stats WHERE chat_id=$1 AND reaction_count > 0 ORDER BY reaction_count DESC LIMIT 1', chat_id)
        
        # 5. Длинное сообщение (ДОБАВИЛИ content В ЗАПРОС)
        long_msg = await conn.fetchrow('SELECT full_name, length, content FROM message_stats WHERE chat_id=$1 ORDER BY length DESC LIMIT 1', chat_id)

    report = "📊 **Статистика чата:**\n\n"
    has_data = False

    if user:
        report += f"🗣 **Болтун:** {user['full_name']} ({user['msg_count']} сообщ.)\n"
        has_data = True
        
    if word:
        report += f"🔤 **Слово:** \"{word['word']}\" ({word['count']} раз)\n"
        has_data = True
        
    if long_msg:
        # Берем текст сообщения
        content = long_msg['content']
        # Если сообщение длиннее 60 символов, обрезаем и ставим троеточие, чтобы не спамить
        if len(content) > 60:
            content = content[:60] + "..."
            
        report += f"📜 **Длиннопост:** {long_msg['full_name']} ({long_msg['length']} симв.):\n_«{content}»_\n"
        has_data = True
        
    if reaction:
        preview = reaction['content'][:20] + "..." if len(reaction['content']) > 20 else reaction['content']
        report += f"🔥 **Хайп:** {reaction['full_name']} (+{reaction['reaction_count']} на \"{preview}\")\n"
        has_data = True

    if not has_data and not sticker:
        await message.answer("❌ Данных пока нет. Напишите что-нибудь!")
        return

    await message.answer(report, parse_mode="Markdown")
    
    if sticker:
        await message.answer_sticker(sticker['file_id'])
        await message.answer(f"🏆 Топ стикер ({sticker['count']} раз)")
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer("Привет! Я считаю статистику. Убедись, что я админ и напиши /stats чтобы увидеть.")

@dp.my_chat_member()
async def on_bot_status_change(event: types.ChatMemberUpdated):
    chat_id = event.chat.id
    new_status = event.new_chat_member.status
    old_status = event.old_chat_member.status

    # Если бот был добавлен в чат
    if new_status not in (ChatMemberStatus.LEFT, ChatMemberStatus.KICKED) and old_status in (ChatMemberStatus.LEFT, ChatMemberStatus.KICKED):
        print(f"Бот добавлен в чат: {event.chat.title or event.chat.id}")
        await bot.send_message(
            chat_id,
            "👋 Привет! Я бот для сбора статистики. "
            "Для получения полной статистики, пожалуйста, убедитесь, что я имею права администратора. "
            "Вы можете посмотреть текущую статистику с помощью команды /stats."
        )
        # Здесь вы можете также вызывать init_db() или другие необходимые действия при добавлении бота

    # Если бот был удален из чата
    elif new_status in (ChatMemberStatus.LEFT, ChatMemberStatus.KICKED):
        print(f"Бот удален из чата: {event.chat.title or event.chat.id}")
        await delete_chat_data(chat_id) # Очищаем данные, как и раньше
        await bot.send_message(chat_id, "До свидания! Все данные чата были удалены.")


# 3. Ловим стикеры
@dp.message(F.sticker)
async def count_stickers(message: types.Message):
    async with db_pool.acquire() as conn:
        await conn.execute('''
            INSERT INTO sticker_stats (chat_id, unique_id, file_id, count) VALUES ($1, $2, $3, 1)
            ON CONFLICT (chat_id, unique_id) DO UPDATE SET count = sticker_stats.count + 1, file_id = EXCLUDED.file_id
        ''', message.chat.id, message.sticker.file_unique_id, message.sticker.file_id)

# 4. Ловим реакции (Нужно явно разрешить updates)
@dp.message_reaction()
async def track_reactions(event: MessageReactionUpdated):
    chat_id = event.chat.id
    message_id = event.message_id
    count = len(event.new_reaction)
    
    async with db_pool.acquire() as conn:
        await conn.execute('UPDATE message_stats SET reaction_count = $1 WHERE chat_id = $2 AND message_id = $3', count, chat_id, message_id)

# 5. Ловим ВЕСЬ остальной текст (В самом низу!)
@dp.message(F.text)
async def process_text_message(message: types.Message):
    # Если это команда (начинается с /), игнорируем, чтобы не засорять базу
    if message.text.startswith("/"): return

    chat_id = message.chat.id
    user_id = message.from_user.id
    name = message.from_user.full_name
    text = message.text

    async with db_pool.acquire() as conn:
        # Активность
        await conn.execute('''
            INSERT INTO user_stats (chat_id, user_id, full_name, msg_count) VALUES ($1, $2, $3, 1)
            ON CONFLICT (chat_id, user_id) DO UPDATE SET msg_count = user_stats.msg_count + 1, full_name = EXCLUDED.full_name
        ''', chat_id, user_id, name)
        
        # Сохранение сообщения
        await conn.execute('INSERT INTO message_stats (chat_id, message_id, user_id, full_name, content, length, reaction_count) VALUES ($1, $2, $3, $4, $5, $6, 0)', 
                           chat_id, message.message_id, user_id, name, text, len(text))
        
        # Слова
        for word in clean_and_split_text(text):
            await conn.execute('''
                INSERT INTO word_stats (chat_id, word, count) VALUES ($1, $2, 1)
                ON CONFLICT (chat_id, word) DO UPDATE SET count = word_stats.count + 1
            ''', chat_id, word)

async def main():
    await init_db()
    await bot.set_my_commands([BotCommand(command="stats", description="Показать статистику")])
    await bot.delete_webhook(drop_pending_updates=True)
    
    # ВАЖНО: Разрешаем получать реакции
    await dp.start_polling(bot, allowed_updates=["message", "message_reaction", "chat_member", "my_chat_member"])

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Бот выключен")