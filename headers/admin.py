# handlers/admin.py

import random
import string
from telebot import types
from config import ADMIN_TELEGRAM_ID
from database import get_pending_teacher_by_code, complete_teacher_registration
from keyboards import admin_main_menu

admin_code_states = set()

def register_admin_handlers(bot):
    
    @bot.message_handler(commands=['admin'])
    def admin_panel(message):
        if message.from_user.id != int(ADMIN_TELEGRAM_ID):
            return
        bot.send_message(
            message.chat.id,
            "👑 <b>Admin Paneliga xush kelibsiz!</b>",
            reply_markup=admin_main_menu(),
            parse_mode="HTML"
        )

    # Admin "Yangi o'qituvchi kiritish" tugmasini bosganda
    @bot.message_handler(func=lambda msg: msg.text == "➕ Yangi o'qituvchi kiritish")
    def ask_teacher_code(message):
        if message.from_user.id != int(ADMIN_TELEGRAM_ID):
            return
            
        admin_code_states.add(message.from_user.id)
        bot.send_message(
            message.chat.id,
            "Iltimos, o'qituvchi yuborgan <b>kodni</b> kiriting (masalan: <code>TCH-1234</code>):",
            parse_mode="HTML"
        )

    # Admin kodni kiritganda
    @bot.message_handler(func=lambda msg: msg.from_user.id in admin_code_states and not msg.text.startswith("/"))
    def check_teacher_code(message):
        if message.from_user.id != int(ADMIN_TELEGRAM_ID):
            return
            
        code = message.text.strip().upper()
        
        # 'yangi' statusli o'qituvchini qidiramiz
        pending_teacher = get_pending_teacher_by_code(code)
        
        admin_code_states.discard(message.from_user.id)
        
        if not pending_teacher:
            bot.send_message(
                message.chat.id,
                "❌ <b>Bunday kod mavjud emas yoki u allaqachon tasdiqlangan!</b>",
                reply_markup=admin_main_menu(),
                parse_mode="HTML"
            )
            return
            
        # pending_teacher = (id, first_name, telegram_id, code, status)
        _, first_name, telegram_id, _, _ = pending_teacher
        
        # Endi o'qituvchining to'liq ismi va familiyasini so'raymiz
        msg = bot.send_message(
            message.chat.id,
            f"✅ Kod topildi!\n"
            f"Kiritgan ism: <b>{first_name}</b>\n\n"
            f"Endi o'qituvchining <b>to'liq Ism va Familiyasini</b> kiriting:",
            parse_mode="HTML"
        )
        bot.register_next_step_handler(msg, lambda m: process_full_name_and_generate(m, telegram_id, code))

    def process_full_name_and_generate(message, telegram_id, code):
        full_name = message.text.strip()
        
        # Login va parol generatsiya qilamiz
        username = f"teacher_{random.randint(100, 999)}"
        password = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
        
        # Bazaga saqlaymiz va statusni yangilaymiz
        teacher_id = complete_teacher_registration(telegram_id, full_name, username, password, code)
        
        if teacher_id:
            bot.send_message(
                message.chat.id,
                f"🎉 <b>O'qituvchi muvaffaqiyatli ro'yxatdan o'tdi!</b>\n\n"
                f"👤 F.I.Sh: <b>{full_name}</b>\n"
                f"🆔 Telegram ID: <code>{telegram_id}</code>\n\n"
                f"🔑 <b>Generatsiya qilingan login/parol:</b>\n"
                f"Login: <code>{username}</code>\n"
                f"Parol: <code>{password}</code>\n\n"
                f"<i>Ushbu ma'lumotlarni o'qituvchiga yuborishingiz mumkin.</i>",
                parse_mode="HTML",
                reply_markup=admin_main_menu()
            )
            
            # O'qituvchining o'ziga ham xabar yuborishimiz mumkin
            try:
                bot.send_message(
                    telegram_id,
                    f"✅ Tabriklaymiz! Admin ma'lumotlaringizni tasdiqladi.\n\n"
                    f"Tizimga kirish uchun ma'lumotlaringiz:\n"
                    f"Login: <code>{username}</code>\n"
                    f"Parol: <code>{password}</code>\n\n"
                    f"Botga qayta /start berib, login va parolingizni yuboring.",
                    parse_mode="HTML"
                )
            except Exception:
                pass
        else:
            bot.send_message(
                message.chat.id,
                "❌ Bazaga saqlashda xatolik yuz berdi.",
                reply_markup=admin_main_menu()
            )