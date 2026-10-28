import json
import os
from datetime import datetime
from telebot import TeleBot
from telebot.types import Message
from database import init_db

from config import TOKEN, ADMIN_TELEGRAM_ID
import config
from headers.teacher import register_teacher_handlers      

bot = TeleBot(TOKEN)

# logs.json fayliga yozish uchun yordamchi funksiya
def write_to_json_log(user_type, first_name, user_id, text):
    log_file = "logs.json"
    log_data = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "user_type": user_type,
        "first_name": first_name,
        "telegram_id": user_id,
        "message": text
    }
    
    # Agar fayl mavjud bo'lmasa yoki bo'sh bo'lsa, uni ro'yxat (list) ko'rinishida boshlaymiz
    if not os.path.exists(log_file) or os.path.getsize(log_file) == 0:
        logs = [log_data]
    else:
        try:
            with open(log_file, "r", encoding="utf-8") as f:
                logs = json.load(f)
            if not isinstance(logs, list):
                logs = []
        except json.JSONDecodeError:
            logs = []
            
        logs.append(log_data)
        
    # Yangilangan ro'yxatni faylga chiroyli formatda (indent=4) yozamiz
    with open(log_file, "w", encoding="utf-8") as f:
        json.dump(logs, f, ensure_ascii=False, indent=4)


@bot.message_handler(commands=["start"])
def start_handler(message: Message):
    if message.chat.id == int( ADMIN_TELEGRAM_ID):
        log_msg = f"Admin: {message.chat.first_name} {message.chat.id}"
        print(log_msg)
        write_to_json_log("Admin", message.chat.first_name, message.chat.id, message.text)
        bot.send_message(message.chat.id, "Salom, admin! Bot ishga tushdi.")
        
    else:
        log_msg = f"User: {message.chat.first_name} {message.chat.id}"
        print(log_msg)
        write_to_json_log("User", message.chat.first_name, message.chat.id, message.text)
        bot.send_message(message.chat.id, "Salom! Bot ishga tushdi.")

def main():
    init_db()
    
    # register_student_handlers(bot)
    register_teacher_handlers(bot)
    # register_admin_handlers(bot)

    print("Bot muvaffaqiyatli ishga tushdi va ishlamoqda...")
    bot.infinity_polling()

if __name__ == "__main__":
    main()