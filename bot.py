import os
TOKEN = os.environ.get('TOKEN')
if TOKEN is None:
    print("ОШИБКА: TOKEN не задан в переменных окружения!")
else:
    print(f"Токен загружен, длина: {len(TOKEN)}")
import threading
from flask import Flask
import telebot
from telebot import types
from time import time
import datetime

# ===== НАСТРОЙКИ =====
ADMIN_ID = 5096008275                 # твой Telegram ID (число)
CHANNEL_ID = "@Ani_Rain"         # username канала (с @) или числовой ID в кавычках, например "-1001234567890"
# =====================

bot = telebot.TeleBot(TOKEN)

# Хранилища
user_last_msg = {}      # для антифлуда
reply_mode = {}          # режим ответа админа: {admin_id: target_user_id}
pending_posts = {}       # сохранённые данные постов: {admin_message_id: post_data}

# Логирование в файл
def log(user_id, username):
    pass
    with open("log.txt", "a", encoding="utf-8") as f:
        f.write(f"{datetime.datetime.now()} - {user_id} (@{username})\n")

# ===== ОБРАБОТЧИК КОМАНДЫ /start =====
@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(message.chat.id,
                     "✨ Добро пожаловать в Общество душ, отправь мне арт, эдит или идею — я передам капитану!\n"
                     "Можнешь скинуть фото, видео, GIF, файл или просто текст.")

# ===== ОБРАБОТЧИК ОТВЕТОВ АДМИНА (ДОЛЖЕН БЫТЬ ПЕРВЫМ) =====
@bot.message_handler(func=lambda m: m.from_user.id == ADMIN_ID and m.from_user.id in reply_mode)
def admin_reply(message):
    target_id = reply_mode.pop(message.from_user.id)   # забираем ID пользователя
    bot.send_message(target_id, f"📨 Ответ от капитана:\n{message.text}")
    bot.reply_to(message, "✅ Ответ отправлен")
    # Возвращаем True, чтобы TeleBot не искал другие обработчики для этого сообщения
    return True

# ===== ОСНОВНОЙ ОБРАБОТЧИК (ПРИЁМ ПОСТОВ) =====
@bot.message_handler(content_types=['text', 'photo', 'video', 'document', 'audio', 'voice', 'animation', 'sticker'])
def handle_content(message):
    user = message.from_user
    user_id = user.id
    username = f"@{user.username}" if user.username else user.first_name
    print(f"Получено сообщение от {user_id}, тип: {message.content_type}")

    # 1. Антифлуд
    now = time()
    if user_id in user_last_msg and now - user_last_msg[user_id] < 30:
        bot.reply_to(message, "⏳ Подожди 30 секунд перед следующим постом.")
        return
    user_last_msg[user_id] = now

    # 2. Если админ в режиме ответа — пропускаем (не обрабатываем как новый пост)
    if message.from_user.id == ADMIN_ID and message.from_user.id in reply_mode:
        return

    # 3. Логируем
    #log(user_id, user.username or "no_username")

    # 4. Подпись для админа (с ID пользователя)
    user_link = f'<a href="tg://user?id={user_id}">{username}</a>'
    admin_caption = f"📬 Новое предложение от {user_link}\nID: {user_id}"
    if message.caption:
        admin_caption += f"\n\n{message.caption}"
    elif message.text:
        admin_caption += f"\n\n{message.text}"

    # 5. Данные для будущей публикации в канал (без ID)
    display_name = f"@{user.username}" if user.username else user.first_name
    post_data = {
        'user_id': user_id,
        'display_name': display_name,
        'content_type': None,
        'file_id': None,
        'text': None,
        'caption': message.caption or message.text
    }

    # 6. Отправляем админу (сначала без кнопок, чтобы получить message_id)
    try:
        if message.photo:
            sent = bot.send_photo(ADMIN_ID, message.photo[-1].file_id, caption=admin_caption, parse_mode='HTML')
            post_data['content_type'] = 'photo'
            post_data['file_id'] = message.photo[-1].file_id
        elif message.video:
            sent = bot.send_video(ADMIN_ID, message.video.file_id, caption=admin_caption, parse_mode='HTML')
            post_data['content_type'] = 'video'
            post_data['file_id'] = message.video.file_id
        elif message.animation:
            sent = bot.send_animation(ADMIN_ID, message.animation.file_id, caption=admin_caption, parse_mode='HTML')
            post_data['content_type'] = 'animation'
            post_data['file_id'] = message.animation.file_id
        elif message.document:
            sent = bot.send_document(ADMIN_ID, message.document.file_id, caption=admin_caption, parse_mode='HTML')
            post_data['content_type'] = 'document'
            post_data['file_id'] = message.document.file_id
        elif message.audio:
            sent = bot.send_audio(ADMIN_ID, message.audio.file_id, caption=admin_caption, parse_mode='HTML')
            post_data['content_type'] = 'audio'
            post_data['file_id'] = message.audio.file_id
        elif message.voice:
            sent = bot.send_voice(ADMIN_ID, message.voice.file_id, caption=admin_caption, parse_mode='HTML')
            post_data['content_type'] = 'voice'
            post_data['file_id'] = message.voice.file_id
        elif message.sticker:
            sent = bot.send_sticker(ADMIN_ID, message.sticker.file_id)
            bot.send_message(ADMIN_ID, admin_caption, parse_mode='HTML')
            post_data['content_type'] = 'sticker'
            post_data['file_id'] = message.sticker.file_id
        else:  # text
            sent = bot.send_message(ADMIN_ID, admin_caption, parse_mode='HTML')
            post_data['content_type'] = 'text'
            post_data['text'] = message.text
    except Exception as e:
        bot.send_message(ADMIN_ID, f"❌ Ошибка при отправке от {user_link}\n{e}", parse_mode='HTML')
        bot.reply_to(message, "⚠️ Техническая ошибка. Попробуй позже.")
        return

    # 7. Сохраняем данные под message_id сообщения админа
    pending_posts[sent.message_id] = post_data

    # 8. Добавляем кнопки к этому сообщению
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("✅ Опубликовать", callback_data=f"pub_{sent.message_id}"),
        types.InlineKeyboardButton("❌ Удалить", callback_data=f"del_{sent.message_id}"),
        types.InlineKeyboardButton("👤 Ответить", callback_data=f"reply_{user_id}")
    )
    bot.edit_message_reply_markup(ADMIN_ID, sent.message_id, reply_markup=markup)

    # 9. Подтверждение пользователю
    bot.reply_to(message, "✅ Отправлено! Если Айзен-сама одобрит — пост появится в канале.")

# ===== ОБРАБОТЧИК НАЖАТИЙ КНОПОК (ДЛЯ АДМИНА) =====
@bot.callback_query_handler(func=lambda call: True)
def callback_inline(call):
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "Ты не капитан", show_alert=True)
        return

    if call.data.startswith('pub_'):
        msg_id = int(call.data.split('_')[1])
        post = pending_posts.get(msg_id)
        if not post:
            bot.answer_callback_query(call.id, "Пост уже обработан или данные потеряны", show_alert=True)
            return

        # Формируем подпись для канала
        sign = f"Предложил: {post['display_name']}"

        try:
            if post['content_type'] == 'photo':
                new_caption = sign
                if post['caption']:
                    new_caption += f"\n\n{post['caption']}"
                bot.send_photo(CHANNEL_ID, post['file_id'], caption=new_caption)
            elif post['content_type'] == 'video':
                new_caption = sign
                if post['caption']:
                    new_caption += f"\n\n{post['caption']}"
                bot.send_video(CHANNEL_ID, post['file_id'], caption=new_caption)
            elif post['content_type'] == 'animation':
                new_caption = sign
                if post['caption']:
                    new_caption += f"\n\n{post['caption']}"
                bot.send_animation(CHANNEL_ID, post['file_id'], caption=new_caption)
            elif post['content_type'] == 'document':
                new_caption = sign
                if post['caption']:
                    new_caption += f"\n\n{post['caption']}"
                bot.send_document(CHANNEL_ID, post['file_id'], caption=new_caption)
            elif post['content_type'] == 'audio':
                new_caption = sign
                if post['caption']:
                    new_caption += f"\n\n{post['caption']}"
                bot.send_audio(CHANNEL_ID, post['file_id'], caption=new_caption)
            elif post['content_type'] == 'voice':
                new_caption = sign
                if post['caption']:
                    new_caption += f"\n\n{post['caption']}"
                bot.send_voice(CHANNEL_ID, post['file_id'], caption=new_caption)
            elif post['content_type'] == 'sticker':
                bot.send_sticker(CHANNEL_ID, post['file_id'])
                bot.send_message(CHANNEL_ID, sign)
                if post['caption']:
                    bot.send_message(CHANNEL_ID, post['caption'])
            elif post['content_type'] == 'text':
                text_with_sign = f"{sign}\n\n{post['text']}"
                bot.send_message(CHANNEL_ID, text_with_sign)

            # Опционально: уведомить пользователя о публикации
            # bot.send_message(post['user_id'], "✅ Господин Айзен доволен, твой пост опубликован в канале!")

        except Exception as e:
            bot.send_message(ADMIN_ID, f"❌ Ошибка при публикации в канал:\n{e}")
            bot.answer_callback_query(call.id, "Ошибка публикации", show_alert=True)
            return

        # Убираем кнопки у админа
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
        bot.answer_callback_query(call.id, "✅ Пост опубликован в канале!")
        del pending_posts[msg_id]

    elif call.data.startswith('del_'):
        msg_id = int(call.data.split('_')[1])
        bot.delete_message(call.message.chat.id, call.message.message_id)
        bot.answer_callback_query(call.id, "🗑 Удалено")
        if msg_id in pending_posts:
            del pending_posts[msg_id]

    elif call.data.startswith('reply_'):
        user_id = int(call.data.split('_')[1])
        reply_mode[call.from_user.id] = user_id
        bot.answer_callback_query(call.id, "✏️ Ответить")
        bot.send_message(call.from_user.id, "Господин Айзен слушает, введи текст ответа:")

# ===== КОМАНДА СТАТИСТИКИ (ТОЛЬКО ДЛЯ АДМИНА) =====
@bot.message_handler(commands=['stats'])
def stats(message):
    if message.from_user.id == ADMIN_ID:
        try:
            with open("log.txt", "r") as f:
                count = len(f.readlines())
            bot.send_message(ADMIN_ID, f"📊 Всего предложений: {count}")
        except FileNotFoundError:
            bot.send_message(ADMIN_ID, "Пока нет статистики.")
    else:
        bot.reply_to(message, "Эта команда только для капитана.")

# ===== ЗАПУСК =====
app = Flask(__name__)

@app.route('/')
def index():
    return "Bot is running!"

def run_flask():
    app.run(host='0.0.0.0', port=10000)

threading.Thread(target=run_flask).start()

if __name__ == '__main__':
    try:
    print("Бот запущен...")
    bot.polling(none_stop=True, interval=0)
except Exception as e:
    print(f"КРИТИЧЕСКАЯ ОШИБКА: {e}")

    bot.polling(none_stop=True, interval=0)



