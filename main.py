from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters
import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TOKEN")
ADMIN_CHAT_ID_1 = os.getenv("ADMIN_1")
ADMIN_CHAT_ID_2 = os.getenv("ADMIN_2")

# Этапы диалога
START, EXPERIENCE, TIME_PER_DAY, MOTIVATION = range(4)

# Кнопки для админов
def admin_keyboard(applicant_id):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Принять", callback_data=f"accept_{applicant_id}")],
        [InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{applicant_id}")]
    ])

# /start — начало диалога
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    button = [[InlineKeyboardButton("Подать заявку", callback_data="apply")]]
    markup = InlineKeyboardMarkup(button)
    await update.message.reply_text(
        "🚀 Привет! Это бот для подачи заявок в нашу команду.",
        reply_markup=markup
    )
    return START

# Обработка кнопки "Подать заявку"
async def apply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("💼 Был ли у вас опыт в этой сфере? (Да/Нет)")
    return EXPERIENCE

# Сохраняем опыт и спрашиваем время
async def experience(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['experience'] = update.message.text
    await update.message.reply_text("⏳ Сколько часов в день готовы уделять работе? (Цифра)")
    return TIME_PER_DAY

# Сохраняем время и спрашиваем мотивацию
async def time_per_day(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['time_per_day'] = update.message.text
    await update.message.reply_text("🎯 Что хотите получить от работы? (Кратко)")
    return MOTIVATION

# Формируем заявку и отправляем админам
async def motivation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['motivation'] = update.message.text
    user = update.effective_user

    # Текст заявки для админов
    application_text = (
        "📌 *Новая заявка*\n\n"
        f"👤 *Пользователь:* @{user.username} (ID: `{user.id}`)\n"
        f"📝 *Имя:* {user.full_name}\n\n"
        f"💼 *Опыт:* {context.user_data['experience']}\n"
        f"⏳ *Время в день:* {context.user_data['time_per_day']} ч.\n"
        f"🎯 *Цель:* {context.user_data['motivation']}"
    )

    # Отправка админам
    for admin_chat_id in [ADMIN_CHAT_ID_1, ADMIN_CHAT_ID_2]:
        await context.bot.send_message(
            chat_id=admin_chat_id,
            text=application_text,
            parse_mode="Markdown",
            reply_markup=admin_keyboard(user.id)
        )

    await update.message.reply_text("✅ Заявка отправлена! Ожидайте ответа.")
    return ConversationHandler.END

# Обработка действий админа (без указания имени)
async def admin_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    action, user_id = query.data.split('_')

    if action == "accept":
        await query.answer("Заявка одобрена")
        await context.bot.send_message(
            chat_id=user_id,
            text="🎉 Ваша заявка одобрена! С вами свяжутся."
        )
    elif action == "reject":
        await query.answer("Заявка отклонена")
        await context.bot.send_message(
            chat_id=user_id,
            text="😕 Ваша заявка отклонена."
        )

    await query.edit_message_reply_markup(reply_markup=None)  # Убираем кнопки

# Запуск бота
def main():
    app = Application.builder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start), CallbackQueryHandler(apply, pattern="^apply$")],
        states={
            EXPERIENCE: [MessageHandler(filters.TEXT, experience)],
            TIME_PER_DAY: [MessageHandler(filters.TEXT, time_per_day)],
            MOTIVATION: [MessageHandler(filters.TEXT, motivation)],
        },
        fallbacks=[]
    )

    app.add_handler(conv_handler)
    app.add_handler(CallbackQueryHandler(admin_action, pattern="^(accept|reject)_"))
    app.run_polling()

if __name__ == '__main__':
    main()
