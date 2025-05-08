import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters,
    ConversationHandler
)

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Конфигурация (отдельные переменные для каждого админа)
TOKEN = os.getenv("TOKEN")
ADMIN_1 = os.getenv("ADMIN_1")  # Первый администратор
ADMIN_2 = os.getenv("ADMIN_2")  # Второй администратор

# Фильтруем только валидные ID админов
ADMIN_IDS = []
if ADMIN_1 and ADMIN_1.isdigit():
    ADMIN_IDS.append(int(ADMIN_1))
if ADMIN_2 and ADMIN_2.isdigit():
    ADMIN_IDS.append(int(ADMIN_2))

# Этапы диалога
START, EXPERIENCE, TIME_PER_DAY, MOTIVATION = range(4)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Начало диалога с кнопкой"""
    keyboard = [[InlineKeyboardButton("Подать заявку", callback_data="apply")]]
    await update.message.reply_text(
        "👋 Добро пожаловать в бот для подачи заявок!\n\n"
        "Нажмите кнопку ниже, чтобы начать:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return START

async def apply_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка нажатия кнопки"""
    query = update.callback_query
    await query.answer()  # Обязательно подтверждаем получение callback
    await query.edit_message_text("💼 Есть ли у вас опыт в этой сфере? (Да/Нет)")
    return EXPERIENCE

async def get_experience(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Получаем информацию об опыте"""
    context.user_data['experience'] = update.message.text
    await update.message.reply_text("⏳ Сколько часов в день готовы уделять работе? (Цифра)")
    return TIME_PER_DAY

async def get_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Получаем информацию о времени"""
    context.user_data['time'] = update.message.text
    await update.message.reply_text("🎯 Почему вы хотите присоединиться к команде?")
    return MOTIVATION

async def get_motivation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Завершаем заявку и отправляем админам"""
    context.user_data['motivation'] = update.message.text
    user = update.effective_user
    
    # Формируем сообщение для админов
    admin_message = (
        "📌 *Новая заявка*\n\n"
        f"👤 *Имя:* {user.full_name}\n"
        f"📱 *Username:* @{user.username or 'нет'}\n"
        f"🆔 *ID:* {user.id}\n\n"
        f"💼 *Опыт:* {context.user_data['experience']}\n"
        f"⏳ *Время:* {context.user_data['time']} ч/день\n"
        f"🎯 *Мотивация:* {context.user_data['motivation']}"
    )
    
    # Кнопки для админов
    keyboard = [
        [
            InlineKeyboardButton("✅ Одобрить", callback_data=f"approve_{user.id}"),
            InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{user.id}")
        ]
    ]
    
    # Отправляем каждому админу
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=admin_message,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except Exception as e:
            logger.error(f"Ошибка отправки админу {admin_id}: {e}")

    await update.message.reply_text("✅ Ваша заявка отправлена! Ожидайте ответа.")
    return ConversationHandler.END

async def admin_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработка действий админов"""
    query = update.callback_query
    await query.answer()
    
    try:
        action, user_id = query.data.split('_')
        if action == "approve":
            await context.bot.send_message(
                chat_id=user_id,
                text="🎉 Ваша заявка одобрена! Скоро с вами свяжутся."
            )
        else:
            await context.bot.send_message(
                chat_id=user_id,
                text="😕 К сожалению, ваша заявка отклонена."
            )
        
        # Удаляем кнопки после ответа
        await query.edit_message_reply_markup()
    except Exception as e:
        logger.error(f"Ошибка обработки действия админа: {e}")
        await query.answer("Произошла ошибка")

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отмена диалога"""
    await update.message.reply_text("❌ Диалог прерван. Напишите /start чтобы начать заново.")
    return ConversationHandler.END

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработка ошибок"""
    logger.error("Ошибка в обработчике", exc_info=context.error)

def main() -> None:
    """Запуск бота"""
    app = Application.builder().token(TOKEN).build()

    # Настройка ConversationHandler
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler('start', start),
            CallbackQueryHandler(apply_button, pattern="^apply$")
        ],
        states={
            EXPERIENCE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_experience)],
            TIME_PER_DAY: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_time)],
            MOTIVATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_motivation)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        allow_reentry=True
    )

    # Регистрация обработчиков
    app.add_handler(conv_handler)
    app.add_handler(CallbackQueryHandler(admin_action, pattern=r"^(approve|reject)_"))
    app.add_error_handler(error_handler)

    # Запуск бота с настройками для Render
    app.run_polling(
        drop_pending_updates=True,
        poll_interval=3.0,
        close_loop=False
    )

if __name__ == '__main__':
    main()
