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

# Конфигурация
TOKEN = os.getenv("TOKEN")
ADMIN_CHAT_IDS = [id for id in [os.getenv(f"ADMIN_{i}") for i in range(1, 3)] if id]

# Этапы диалога
START, EXPERIENCE, TIME_PER_DAY, MOTIVATION = range(4)

# Клавиатура для админов
def get_admin_keyboard(applicant_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Принять", callback_data=f"accept_{applicant_id}"),
            InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{applicant_id}")
        ]
    ])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка команды /start - начало диалога."""
    keyboard = [[InlineKeyboardButton("Подать заявку", callback_data="apply")]]
    await update.message.reply_text(
        "🚀 Привет! Это бот для подачи заявок в нашу команду.",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return START

async def apply(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка кнопки 'Подать заявку'."""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("💼 Был ли у вас опыт в этой сфере? (Да/Нет)")
    return EXPERIENCE

async def experience(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Сохраняем опыт и спрашиваем время."""
    context.user_data['experience'] = update.message.text[:100]  # Ограничиваем длину
    await update.message.reply_text("⏳ Сколько часов в день готовы уделять работе? (Цифра)")
    return TIME_PER_DAY

async def time_per_day(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Сохраняем время и спрашиваем мотивацию."""
    try:
        # Проверяем, что введено число
        hours = float(update.message.text.replace(',', '.'))
        context.user_data['time_per_day'] = f"{hours} ч."
    except ValueError:
        context.user_data['time_per_day'] = update.message.text[:50]
    
    await update.message.reply_text("🎯 Что хотите получить от работы? (Кратко)")
    return MOTIVATION

async def motivation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Формируем заявку и отправляем админам."""
    context.user_data['motivation'] = update.message.text[:300]  # Ограничиваем длину
    user = update.effective_user

    # Формируем текст заявки
    application_text = (
        "📌 *Новая заявка*\n\n"
        f"👤 *Пользователь:* @{user.username or 'нет'}\n"
        f"🆔 *ID:* `{user.id}`\n"
        f"📝 *Имя:* {user.full_name}\n\n"
        f"💼 *Опыт:* {context.user_data.get('experience', 'не указано')}\n"
        f"⏳ *Время в день:* {context.user_data.get('time_per_day', 'не указано')}\n"
        f"🎯 *Цель:* {context.user_data.get('motivation', 'не указано')}"
    )

    # Отправка всем админам
    for admin_chat_id in ADMIN_CHAT_IDS:
        try:
            await context.bot.send_message(
                chat_id=admin_chat_id,
                text=application_text,
                parse_mode="Markdown",
                reply_markup=get_admin_keyboard(user.id)
            )
        except Exception as e:
            logger.error(f"Ошибка отправки сообщения админу {admin_chat_id}: {e}")

    await update.message.reply_text("✅ Заявка отправлена! Ожидайте ответа.")
    return ConversationHandler.END

async def admin_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработка действий админа (принять/отклонить)."""
    query = update.callback_query
    await query.answer()
    
    try:
        action, user_id = query.data.split('_')
        user_id = int(user_id)
        
        if action == "accept":
            response_text = "🎉 Ваша заявка одобрена! С вами свяжутся."
        else:
            response_text = "😕 Ваша заявка отклонена."
        
        await context.bot.send_message(chat_id=user_id, text=response_text)
        await query.edit_message_reply_markup()  # Убираем кнопки
        
    except Exception as e:
        logger.error(f"Ошибка обработки действия админа: {e}")
        await query.answer("Произошла ошибка")

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отмена диалога."""
    await update.message.reply_text("Диалог прерван. Напишите /start чтобы начать заново.")
    return ConversationHandler.END

async def post_init(application: Application) -> None:
    """Действия после инициализации бота."""
    await application.bot.delete_webhook(drop_pending_updates=True)
    logger.info("Бот успешно запущен")

async def post_stop(application: Application) -> None:
    """Действия при остановке бота."""
    logger.info("Бот остановлен")

def main() -> None:
    """Запуск бота."""
    # Создаем Application с обработчиками событий
    app = Application.builder() \
        .token(TOKEN) \
        .post_init(post_init) \
        .post_stop(post_stop) \
        .build()

    # Обработчик диалога с явным указанием per_message=True
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler('start', start),
            CallbackQueryHandler(apply, pattern="^apply$")
        ],
        states={
            EXPERIENCE: [MessageHandler(filters.TEXT & ~filters.COMMAND, experience)],
            TIME_PER_DAY: [MessageHandler(filters.TEXT & ~filters.COMMAND, time_per_day)],
            MOTIVATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, motivation)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        per_message=True,  # Важно для корректной работы CallbackQuery
        allow_reentry=True
    )

    # Регистрируем обработчики
    app.add_handler(conv_handler)
    app.add_handler(CallbackQueryHandler(admin_action, pattern=r"^(accept|reject)_\d+$"))
    app.add_handler(CommandHandler('cancel', cancel))

    # Обработчик ошибок
    app.add_error_handler(lambda u, c: logger.error("Ошибка в обработчике", exc_info=c.error))

    # Запускаем бота с оптимизациями для Render
    app.run_polling(
        poll_interval=2.0,  # Увеличенный интервал для Render Free
        drop_pending_updates=True,
        close_loop=False,
        stop_signals=None  # Для корректной обработки сигналов остановки
    )

if __name__ == '__main__':
    main()
