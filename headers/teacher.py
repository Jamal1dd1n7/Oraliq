import random
from telebot import types
from keyboards import teacher_main_menu
from database import check_teacher_by_telegram_id, add_pending_teacher, verify_teacher_login

# Holatlarni boshqarish uchun lug'atlar va setlar
teacher_name_states = set()
teacher_login_step = set()        # Login kiritishini kutayotganlar
teacher_password_step = {}        # {telegram_id: login} - parolni kutayotganlar va ularning loginlari

def register_teacher_handlers(bot):
    
    @bot.message_handler(func=lambda msg: msg.text == "👨‍🏫 O'qituvchi")
    def teacher_entry_point(message):
        telegram_id = message.from_user.id
        
        # 1. Bazadan tekshiramiz
        teacher = check_teacher_by_telegram_id(telegram_id)
        if teacher:
            # Agar bazada bo'lsa -> ALOHIDA LOGIN SO'RAYMIZ
            teacher_login_step.add(telegram_id)
            bot.send_message(
                message.chat.id,
                "Sizning profilingiz mavjud.\n\n"
                "Iltimos, tizimga kirish uchun <b>loginingizni</b> kiriting:",
                parse_mode="HTML"
            )
        else:
            # Bazada yo'q bo'lsa -> Ismini so'raymiz
            teacher_name_states.add(telegram_id)
            bot.send_message(
                message.chat.id,
                "❌ Siz bazada yo'qsiz.\n"
                "O'qituvchilar qatoriga qo'shilish uchun <b>ismingizni</b> kiriting:",
                parse_mode="HTML"
            )

    # O'qituvchi ismini yuborganda
    @bot.message_handler(func=lambda msg: msg.from_user.id in teacher_name_states and not msg.text.startswith("/"))
    def process_teacher_name(message):
        telegram_id = message.from_user.id
        first_name = message.text.strip()
        
        code = f"TCH-{random.randint(1000, 9999)}"
        success = add_pending_teacher(first_name, telegram_id, code)
        teacher_name_states.discard(telegram_id)
        
        if success:
            bot.send_message(
                message.chat.id,
                f"✅ Ma'lumotlaringiz qabul qilindi!\n\n"
                f"Sizning ro'yxatdan o'tish kodingiz: <code>{code}</code>\n"
                f"Iltimos, admin tasdiqlashini kuting. Admin kodni kiritgandan so'ng sizga login va parol beriladi.",
                parse_mode="HTML"
            )
        else:
            bot.send_message(message.chat.id, "❌ Xatolik yuz berdi. Qaytadan urinib ko'ring.")

    # --- 1-QADAM: Loginni alohida qabul qilish ---
    @bot.message_handler(func=lambda msg: msg.from_user.id in teacher_login_step and not msg.text.startswith("/"))
    def process_teacher_login_input(message):
        telegram_id = message.from_user.id
        login = message.text.strip()
        
        # Loginni vaqtincha saqlab, parolni so'raymiz
        teacher_login_step.discard(telegram_id)
        teacher_password_step[telegram_id] = login
        
        bot.send_message(
            message.chat.id,
            "🔑 Endi <b>parolingizni</b> kiriting:",
            parse_mode="HTML"
        )

    # --- 2-QADAM: Parolni alohida qabul qilish va tekshirish ---
    @bot.message_handler(func=lambda msg: msg.from_user.id in teacher_password_step and not msg.text.startswith("/"))
    def process_teacher_password_input(message):
        telegram_id = message.from_user.id
        password = message.text.strip()
        
        # Saqlangan loginni olamiz
        login = teacher_password_step.pop(telegram_id, None)
        
        if not login:
            bot.send_message(message.chat.id, "❌ Xatolik yuz berdi. Iltimos, qaytadan /start bosing.")
            return

        # Login va parolni bazadan tekshiramiz
        teacher = verify_teacher_login(login, password)
        
        if teacher:
            teacher_id, full_name = teacher
            bot.send_message(
                message.chat.id,
                f"✅ Xush kelibsiz, ustoz <b>{full_name}</b>!",
                reply_markup=teacher_main_menu(),
                parse_mode="HTML"
            )
        else:
            bot.send_message(
                message.chat.id,
                "❌ Login yoki parol xato!\n"
                "Qaytadan urinib ko'rish uchun /start buyrug'ini bosing."
            )