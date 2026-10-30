# keyboards.py
from telebot import types
# keyboards.py faylining oxiriga qo'shing:

def days_inline_keyboard():
    markup = types.InlineKeyboardMarkup(row_width=3)
    days = ["Dushanba", "Seshanba", "Chorshanba", "Payshanba", "Juma", "Shanba"]
    for day in days:
        markup.add(types.InlineKeyboardButton(day, callback_data=f"sched_{day}"))
    return markup

def role_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(types.KeyboardButton("👨‍🏫 O'qituvchi"), types.KeyboardButton("Talaba"))
    return markup

def teacher_main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        types.KeyboardButton("📅 Dars jadvali"),
        types.KeyboardButton("📝 Imtihon"),
        types.KeyboardButton("📊 Imtihon natijalari"),
        types.KeyboardButton("⚙️ Sozlamalar")
    )
    return markup

def admin_main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        types.KeyboardButton("➕ Yangi o'qituvchi kiritish"),
        types.KeyboardButton("👥 Yordamchi admin qo'shish"),
        types.KeyboardButton("📅 Dars jadvallarini boshqarish"),
        types.KeyboardButton("📋 Ro'yxatlarni ko'rish")
    )
    return markup