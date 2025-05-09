import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters, ConversationHandler

# Настройка
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
TOKEN = os.getenv("TOKEN")
ADMINS = [int(id) for id in [os.getenv("ADMIN_1"), os.getenv("ADMIN_2")] if id and id.isdigit()]
STEPS = range(4)  # START, EXPERIENCE, TIME, MOTIVATION

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "👋 Добро пожаловать!\nНажмите кнопку ниже:",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📝 Подать заявку", callback_data="apply")]])
    )
    return 0

async def apply(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    await update.callback_query.edit_message_text("💼 Есть опыт? (Да/Нет)")
    return 1

async def experience(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['exp'] = update.message.text[:200]
    await update.message.reply_text("⏳ Часов в день? (Цифра)")
    return 2

async def time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        context.user_data['time'] = f"{float(update.message.text.replace(',', '.')):.1f} ч/день"
    except ValueError:
        await update.message.reply_text("Введите число")
        return 2
    await update.message.reply_text("🎯 Почему вы хотите присоединиться?")
    return 3

async def motivation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    text = (
        f"👤 {user.full_name} (@{user.username or 'нет'})\n"
        f"💼 Опыт: {context.user_data['exp']}\n"
        f"⏳ Время: {context.user_data['time']}\n"
        f"🎯 Цель: {update.message.text[:500]}"
    )
    
    for admin in ADMINS:
        await context.bot.send_message(
            chat_id=admin,
            text=text,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("✅ Принять", callback_data=f"ok_{user.id}"),
                InlineKeyboardButton("❌ Отклонить", callback_data=f"no_{user.id}")
            ]])
        )
    
    await update.message.reply_text("✅ Заявка отправлена!")
    return ConversationHandler.END

async def decide(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    action, user_id = query.data.split('_')
    await context.bot.send_message(user_id, "🎉 Одобрено!" if action == "ok" else "😕 Отклонено")
    await query.edit_message_reply_markup()

def main():
    app = Application.builder().token(TOKEN).build()
    
    conv = ConversationHandler(
        entry_points=[CommandHandler('start', start), CallbackQueryHandler(apply, pattern="^apply$")],
        states={
            1: [MessageHandler(filters.TEXT & ~filters.COMMAND, experience)],
            2: [MessageHandler(filters.TEXT & ~filters.COMMAND, time)],
            3: [MessageHandler(filters.TEXT & ~filters.COMMAND, motivation)]
        },
        fallbacks=[]
    )
    
    app.add_handler(conv)
    app.add_handler(CallbackQueryHandler(decide, pattern=r"^(ok|no)_\d+$"))
    app.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
