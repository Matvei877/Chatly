import asyncio
import logging
import asyncpg
import re
import os
import dotenv
import httpx
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from pymorphy2 import MorphAnalyzer

from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.enums import ChatMemberStatus
from aiogram.types import BotCommand, MessageReactionUpdated, BufferedInputFile, InputMediaPhoto, InputMediaAnimation
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.exceptions import TelegramBadRequest

from main_draw import create_active_user_image, create_top_words_image, create_top_sticker_image, create_top_sticker_gif

logging.basicConfig(level=logging.INFO)
dotenv.load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    try:
        from config import DATABASE_URL as FILE_DB_URL
        DATABASE_URL = FILE_DB_URL
        print("✅ DATABASE_URL загружен из config.py")
    except ImportError:
        print("⚠️ DATABASE_URL не найден ни в переменных, ни в config.py!")
        DATABASE_URL = "" 

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
db_pool = None
morph = MorphAnalyzer()

STOP_WORDS = {
    "и", "в", "не", "на", "я", "что", "с", "а", "то", "как", "у", "все", "но", "по", "он", "она", 
    "так", "же", "от", "о", "ты", "за", "да", "из", "к", "мы", "бы", "вы", "ну", "ли", "ни", "много", 
    "это", "этот", "эта", "эти", "этот", "эту", "этим", "этого", "этой", "этих", "этими", "этом",
    "он", "она", "оно", "они", "его", "её", "их", "ему", "ей", "им", "его", "её", "их", "ним", "ней", "ними",
    "мой", "моя", "моё", "мои", "твой", "твоя", "твоё", "твои", "наш", "наша", "наше", "наши", "ваш", "ваша", "ваше", "ваши",
    "себя", "себе", "собой", "собою",
    "кто", "что", "какой", "какая", "какое", "какие", "чей", "чья", "чьё", "чьи", "который", "которая", "которое", "которые",
    "где", "куда", "откуда", "когда", "почему", "зачем", "как", "сколько", "чей",
    "быть", "был", "была", "было", "были", "будет", "будут", "буду", "будешь", "будем", "будете",
    "есть", "есть", "суть",
    "весь", "вся", "всё", "все", "всего", "всей", "всем", "всеми", "всём",
    "сам", "сама", "само", "сами", "самого", "самой", "самому", "самим", "самими", "самом", "самой",
    "уже", "ещё", "тоже", "только", "лишь", "просто", "даже", "вот", "вон", "тут", "там", "здесь", "туда", "сюда",
    "очень", "совсем", "почти", "чуть", "немного", "много", "мало", "больше", "меньше",
    "или", "либо", "ни", "нибудь", "либо", "ли", "же", "ведь", "хотя", "если", "когда", "пока", "чтобы", "чтоб",
    "без", "для", "до", "из", "к", "на", "над", "о", "об", "от", "перед", "по", "под", "при", "про", "с", "со", "у", "через",
    "можно", "нужно", "надо", "должен", "должна", "должно", "должны", "может", "может", "может", "могут",
    "будет", "будет", "будет", "будут", "стал", "стала", "стало", "стали", "станет", "станут"
}

async def init_db_pool():
    global db_pool
    if not DATABASE_URL:
        print("❌ Ошибка: Нет ссылки на базу данных!")
        return
    try:
        db_pool = await asyncpg.create_pool(dsn=DATABASE_URL)
        async with db_pool.acquire() as connection:
            await connection.execute('''CREATE TABLE IF NOT EXISTS sticker_stats (chat_id BIGINT, unique_id TEXT, file_id TEXT, count INTEGER DEFAULT 1, PRIMARY KEY (chat_id, unique_id))''')
            await connection.execute('''CREATE TABLE IF NOT EXISTS word_stats (chat_id BIGINT, word TEXT, count INTEGER DEFAULT 1, PRIMARY KEY (chat_id, word))''')
            await connection.execute('''CREATE TABLE IF NOT EXISTS user_stats (chat_id BIGINT, user_id BIGINT, full_name TEXT, msg_count INTEGER DEFAULT 1, PRIMARY KEY (chat_id, user_id))''')
            await connection.execute('''CREATE TABLE IF NOT EXISTS message_stats (chat_id BIGINT, message_id BIGINT, user_id BIGINT, full_name TEXT, content TEXT, length INTEGER, reaction_count INTEGER DEFAULT 0, PRIMARY KEY (chat_id, message_id))''')
        print("✅ База данных успешно подключена")
    except Exception as e:
        print(f"❌ Ошибка подключения к БД: {e}")

async def delete_chat_data(chat_id):
    if not db_pool: return
    async with db_pool.acquire() as connection:
        await connection.execute('DELETE FROM sticker_stats WHERE chat_id = $1', chat_id)
        await connection.execute('DELETE FROM word_stats WHERE chat_id = $1', chat_id)
        await connection.execute('DELETE FROM user_stats WHERE chat_id = $1', chat_id)
        await connection.execute('DELETE FROM message_stats WHERE chat_id = $1', chat_id)

def normalize_word(word):
    try:
        parsed = morph.parse(word)[0]
        normal_form = parsed.normal_form
        return normal_form.lower()
    except:
        return word.lower()

def clean_and_split_text(text):
    if not text: return []
    text = re.sub(r'[^\w\s]', '', text.lower())
    words = []
    for w in text.split():
        if len(w) > 2:
            normalized = normalize_word(w)
            if normalized not in STOP_WORDS:
                words.append(normalized)
    return words

async def update_active_user_title(chat_id):
    if not db_pool:
        return
    
    try:
        async with db_pool.acquire() as conn:
            user_row = await conn.fetchrow(
                'SELECT user_id, full_name, msg_count FROM user_stats WHERE chat_id=$1 ORDER BY msg_count DESC LIMIT 1',
                chat_id
            )
            
            if not user_row or user_row['msg_count'] < 10:
                return
            
            user_id = user_row['user_id']
            
            try:
                bot_info = await bot.get_me()
                bot_member = await bot.get_chat_member(chat_id, bot_info.id)
                if bot_member.status != ChatMemberStatus.ADMINISTRATOR:
                    return
                
                if not bot_member.can_promote_members:
                    return
            except:
                return
            
            try:
                user_member = await bot.get_chat_member(chat_id, user_id)
                
                if user_member.status == ChatMemberStatus.ADMINISTRATOR:
                    try:
                        await bot.set_chat_administrator_custom_title(chat_id, user_id, "Самый активный")
                        print(f"✅ Установлен титул 'Самый активный' для пользователя {user_id} в чате {chat_id}")
                    except TelegramBadRequest as e:
                        if "not enough rights" not in str(e).lower():
                            print(f"⚠️ Ошибка установки титула: {e}")
                elif user_member.status == ChatMemberStatus.MEMBER:
                    try:
                        await bot.promote_chat_member(
                            chat_id=chat_id,
                            user_id=user_id,
                            can_manage_chat=False,
                            can_delete_messages=False,
                            can_manage_video_chats=False,
                            can_restrict_members=False,
                            can_promote_members=False,
                            can_change_info=False,
                            can_invite_users=False,
                            can_post_messages=False,
                            can_edit_messages=False,
                            can_pin_messages=False,
                            can_manage_topics=False
                        )
                        await asyncio.sleep(0.5)
                        await bot.set_chat_administrator_custom_title(chat_id, user_id, "Самый активный")
                        print(f"✅ Пользователь {user_id} назначен администратором с титулом 'Самый активный' в чате {chat_id}")
                    except TelegramBadRequest as e:
                        print(f"⚠️ Не удалось назначить администратором: {e}")
            except Exception as e:
                print(f"⚠️ Ошибка при обновлении титула для чата {chat_id}: {e}")
    except Exception as e:
        print(f"⚠️ Ошибка в update_active_user_title: {e}")

async def keep_alive_task():
    url = "https://chatly-backend-nflu.onrender.com/ping" 
    print(f"🔄 Запущен пингер для: {url}")

    while True:
        await asyncio.sleep(600)
        try:
            async with httpx.AsyncClient() as client:
                await client.get(url)
        except Exception as e:
            print(f"⚠️ Ошибка пинга: {e}")

async def update_titles_task():
    if not db_pool:
        return
    
    while True:
        await asyncio.sleep(3600)
        try:
            async with db_pool.acquire() as conn:
                chat_ids = await conn.fetch('SELECT DISTINCT chat_id FROM user_stats')
                for row in chat_ids:
                    chat_id = row['chat_id']
                    try:
                        await update_active_user_title(chat_id)
                    except Exception as e:
                        print(f"⚠️ Ошибка обновления титула для чата {chat_id}: {e}")
        except Exception as e:
            print(f"⚠️ Ошибка в update_titles_task: {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db_pool()
    
    await bot.set_my_commands([BotCommand(command="stats", description="Показать статистику")])
    await bot.delete_webhook(drop_pending_updates=True)
    
    polling_task = asyncio.create_task(dp.start_polling(bot, allowed_updates=["message", "message_reaction", "chat_member", "my_chat_member"]))
    ping_task = asyncio.create_task(keep_alive_task())
    titles_task = asyncio.create_task(update_titles_task())
    
    print("🚀 Сервер и Бот запущены!")
    
    yield
    
    print("🛑 Остановка сервера...")
    polling_task.cancel()
    ping_task.cancel()
    titles_task.cancel()
    try:
        await polling_task
        await ping_task
        await titles_task
    except asyncio.CancelledError:
        pass

    if db_pool:
        await db_pool.close()
    print("👋 Все соединения закрыты.")

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return "Bot is running!"

@app.api_route("/ping", methods=["GET", "HEAD"])
async def ping_server():
    return {"status": "alive"}

@app.get("/api/chat/{chat_id}")
async def get_chat_stats_api(chat_id: int):
    if not db_pool:
        return {"error": "База данных не подключена"}

    async with db_pool.acquire() as conn:
        user_row = await conn.fetchrow('SELECT user_id, full_name, msg_count FROM user_stats WHERE chat_id=$1 ORDER BY msg_count DESC LIMIT 1', chat_id)
        
        active_user_data = None
        if user_row:
            avatar_url = None
            try:
                photos = await bot.get_user_profile_photos(user_row['user_id'])
                if photos.total_count > 0:
                    file_id = photos.photos[0][0].file_id 
                    file_info = await bot.get_file(file_id)
                    avatar_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_info.file_path}"
            except Exception as e:
                print(f"Не удалось получить аватар для API: {e}")

            active_user_data = {
                "name": user_row['full_name'],
                "count": user_row['msg_count'],
                "avatar_url": avatar_url
            }

        words_rows = await conn.fetch('SELECT word, count FROM word_stats WHERE chat_id=$1 ORDER BY count DESC LIMIT 10', chat_id)
        top_words = [{"word": r['word'], "count": r['count']} for r in words_rows]

    return {
        "chat_id": chat_id,
        "active_user": active_user_data,
        "top_words": top_words
    }

@dp.message(Command("stats"))
async def send_stats(message: types.Message):
    chat_id = message.chat.id
    if not db_pool: 
        await message.answer("⚠️ База данных не подключена.")
        return

    user_name = "Никто"
    user_id = None
    msg_count = 0
    avatar_bytes = None
    top_words = [] 
    sticker_file_id = None
    sticker_count = 0
    sticker_bytes = None
    is_video_sticker = False

    async with db_pool.acquire() as conn:
        user_row = await conn.fetchrow('SELECT user_id, full_name, msg_count FROM user_stats WHERE chat_id=$1 ORDER BY msg_count DESC LIMIT 1', chat_id)
        if user_row:
            user_name = user_row['full_name']
            msg_count = user_row['msg_count']
            user_id = user_row['user_id']
        
        words_rows = await conn.fetch('SELECT word, count FROM word_stats WHERE chat_id=$1 ORDER BY count DESC LIMIT 3', chat_id)
        top_words = [(r['word'], r['count']) for r in words_rows]

        sticker_row = await conn.fetchrow('SELECT file_id, count FROM sticker_stats WHERE chat_id=$1 ORDER BY count DESC LIMIT 1', chat_id)
        if sticker_row:
            sticker_file_id = sticker_row['file_id']
            sticker_count = sticker_row['count']

    if user_id:
        try:
            photos = await bot.get_user_profile_photos(user_id)
            if photos.total_count > 0:
                file_id = photos.photos[0][-1].file_id 
                file_info = await bot.get_file(file_id)
                downloaded_file = await bot.download_file(file_info.file_path)
                avatar_bytes = downloaded_file.read()
        except Exception: pass
            
    if sticker_file_id:
        try:
            st_file_info = await bot.get_file(sticker_file_id)
            file_path = st_file_info.file_path
            
            if file_path and file_path.endswith('.webm'):
                st_downloaded = await bot.download_file(file_path)
                sticker_bytes = st_downloaded.read()
                is_video_sticker = True
            elif file_path and file_path.endswith('.tgs'):
                sticker_bytes = None
            else:
                st_downloaded = await bot.download_file(file_path)
                sticker_bytes = st_downloaded.read()
                is_video_sticker = False
        except Exception: 
            sticker_bytes = None
            is_video_sticker = False

    media_group = []
    
    if msg_count > 0:
        try:
            image_active = await asyncio.to_thread(create_active_user_image, avatar_bytes, msg_count, user_name)
            if image_active:
                file_active = BufferedInputFile(image_active.read(), filename="active.png")
                media_group.append(InputMediaPhoto(media=file_active, caption="Статистика чата"))
        except Exception as e:
            print(f"Ошибка генерации картинки active: {e}")

    if top_words:
        try:
            image_words = await asyncio.to_thread(create_top_words_image, top_words)
            if image_words:
                file_words = BufferedInputFile(image_words.read(), filename="words.png")
                media_group.append(InputMediaPhoto(media=file_words))
        except Exception as e:
            print(f"Ошибка генерации картинки words: {e}")

    if sticker_bytes:
        try:
            if is_video_sticker:
                gif_sticker = await asyncio.to_thread(create_top_sticker_gif, sticker_bytes, sticker_count)
                if gif_sticker:
                    file_sticker = BufferedInputFile(gif_sticker.read(), filename="sticker.gif")
                    media_group.append(InputMediaAnimation(media=file_sticker))
            else:
                image_sticker = await asyncio.to_thread(create_top_sticker_image, sticker_bytes, sticker_count)
                if image_sticker:
                    file_sticker = BufferedInputFile(image_sticker.read(), filename="sticker.png")
                    media_group.append(InputMediaPhoto(media=file_sticker))
        except Exception as e:
            print(f"Ошибка генерации картинки sticker: {e}")

    web_url = f"https://chatly1-iota.vercel.app/?id={chat_id}"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Смотреть на сайте", url=web_url)]
    ])

    if media_group:
        await message.answer_media_group(media=media_group)
        await message.answer("👆 Полная статистика и анимация на сайте:", reply_markup=keyboard)
        
        try:
            await update_active_user_title(chat_id)
        except Exception as e:
            print(f"⚠️ Ошибка обновления титула при /stats: {e}")
    else:
        await message.answer("❌ Недостаточно данных для статистики.")

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer("Я считаю статистику. Напиши /stats. (API работает)")

@dp.my_chat_member()
async def on_bot_status_change(event: types.ChatMemberUpdated):
    if event.new_chat_member.status in (ChatMemberStatus.LEFT, ChatMemberStatus.KICKED):
        await delete_chat_data(event.chat.id)

@dp.message(F.sticker)
async def count_stickers(message: types.Message):
    if not db_pool: return
    sticker = message.sticker
    file_id = sticker.file_id
    unique_id = sticker.file_unique_id
    
    async with db_pool.acquire() as conn:
        await conn.execute('''
            INSERT INTO sticker_stats (chat_id, unique_id, file_id, count) VALUES ($1, $2, $3, 1)
            ON CONFLICT (chat_id, unique_id) DO UPDATE SET count = sticker_stats.count + 1, file_id = EXCLUDED.file_id
        ''', message.chat.id, unique_id, file_id)

@dp.message_reaction()
async def track_reactions(event: MessageReactionUpdated):
    if not db_pool: return
    chat_id = event.chat.id
    message_id = event.message_id
    count = len(event.new_reaction)
    async with db_pool.acquire() as conn:
        await conn.execute('UPDATE message_stats SET reaction_count = $1 WHERE chat_id = $2 AND message_id = $3', count, chat_id, message_id)

@dp.message(F.text)
async def process_text_message(message: types.Message):
    if message.text.startswith("/"): return
    if not db_pool: return
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

if __name__ == "__main__":
    port = int(os.getenv("SERVER_PORT", os.getenv("PORT", 8000)))
    print(f"🏁 Запуск сервера на порту {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)