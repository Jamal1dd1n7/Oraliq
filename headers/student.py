from telebot import types
from database import (
    get_connection,
    get_queue_by_code, 
    check_previous_student_finished, 
    set_student_ready_status,
    update_queue_student_telegram_id
)

student_code_steps = set()

def register_student_handlers(bot):

    # 1. Talaba roliga kirish
    @bot.message_handler(func=lambda msg: msg.text == "Talaba")
    def student_entry_point(message):
        student_code_steps.add(message.from_user.id)
        bot.send_message(
            message.chat.id,
            "👨‍🎓 <b>Talaba bo'limiga xush kelibsiz!</b>\n\n"
            "O'qituvchingizdan olgan <b>kirish kodingizni</b> kiriting (masalan: <code>ST-7284</code>):",
            parse_mode="HTML"
        )

    # 2. Kodni qabul qilish, telegram_id ni saqlash va savollarni chiqarish
    @bot.message_handler(func=lambda msg: msg.from_user.id in student_code_steps and not msg.text.startswith("/"))
    def process_student_code(message):
        telegram_id = message.from_user.id
        access_code = message.text.strip().upper()
        
        queue_item = get_queue_by_code(access_code)
        if not queue_item:
            bot.send_message(message.chat.id, "❌ Bunday kod topilmadi yoki xato kiritildi. Qaytadan urinib ko'ring:")
            return
            
        queue_id, exam_id, group_id, student_id, student_name, q_texts, is_ready, status, queue_order = queue_item
        
        # Talabaning telegram_id sini bazaga saqlab qo'yamiz (natija borishi uchun muhim)
        update_queue_student_telegram_id(queue_id, telegram_id)
        
        student_code_steps.discard(telegram_id)
        
        # Talabaga uning savollari va tayyorlanish tugmasini yuboramiz
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("✅ Tayyorman", callback_data=f"student_ready_{queue_id}"))
        
        bot.send_message(
            message.chat.id,
            f"👤 Talaba: <b>{student_name}</b>\n\n"
            f"📝 <b>Sizga berilgan savollar:</b>\n{q_texts}\n\n"
            f"⏳ Savollarni o'qib chiqib, tayyor bo'lganingizda <b>'Tayyorman'</b> tugmasini bosing:",
            reply_markup=markup,
            parse_mode="HTML"
        )

    # 3. "Tayyorman" tugmasi bosilganda
    @bot.callback_query_handler(func=lambda call: call.data.startswith("student_ready_"))
    def handle_student_ready_click(call):
        queue_id = int(call.data.split("_")[2])
        bot.answer_callback_query(call.id)
        
        # Bazadan ma'lumotlarni qayta o'qib olamiz
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT exam_id, group_id, queue_order, student_full_name FROM exam_queue WHERE id = %s", (queue_id,))
        row = cur.fetchone()
        cur.close()
        conn.close()
        
        if not row:
            bot.send_message(call.message.chat.id, "❌ Xatolik yuz berdi.")
            return
            
        exam_id, group_id, queue_order, student_name = row
        
        # Oldingi talabalar tugatganligini tekshiramiz
        is_previous_finished = check_previous_student_finished(exam_id, group_id, queue_order)
        
        if not is_previous_finished:
            # Agar oldingi talaba hali tugatmagan bo'lsa
            set_student_ready_status(queue_id) # Statusni ready qilamiz, lekin navbat kuttiramiz
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=f"✅ Ma'lumotlaringiz qabul qilindi, <b>{student_name}</b>!\n\n"
                     f"⏳ Hozirda sizdan oldingi talaba imtihon topshirmoqda. "
                     f"Iltimos, tayyorlanib turing, navbatingiz kelishi bilan xabar beramiz.",
                parse_mode="HTML"
            )
        else:
            # Agar oldidagilar tugatgan bo'lsa, darhol o'qituvchiga uzatamiz
            set_student_ready_status(queue_id)
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=f"✅ <b>Tayyorsiz!</b> O'qituvchi sizni imtihon olish uchun chaqirmoqda.",
                parse_mode="HTML"
            )