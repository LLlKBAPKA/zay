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
from telegram.helpers import escape_markdown

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Конфигурация
TOKEN = os.getenv("TOKEN")
ADMIN_1 = os.getenv("ADMIN_1")  # ID первого администратора
ADMIN_2 = os.getenv("ADMIN_2")  # ID второго администратора

# Проверяем и фильтруем ID админов
ADMIN_IDS = []
for admin_id in [ADMIN_1, ADMIN_2]:
    if admin_id and admin_id.isdigit():
        ADMIN_IDS.append(int(admin_id))

# Этапы диалога
START, EXPERIENCE, TIME, MOTIVATION = range(4)

# Флаг активности бота
BOT_ACTIVE = True

def is_admin(user_id: int) -> bool:
    """Проверяет, является ли пользователь администратором"""
    return str(user_id) in [ADMIN_1, ADMIN_2]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка команды /start"""
    if not BOT_ACTIVE:
        await update.message.reply_text("⏸ Бот временно отключен администратором")
        return ConversationHandler.END
        
    keyboard = [[InlineKeyboardButton("📝 Подать заявку", callback_data="start_application")]]
    await update.message.reply_text(
        "👋 Добро пожаловать в бот для подачи заявок!\n\n"
        "Нажмите кнопку ниже, чтобы начать:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return START

async def start_application(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Начало подачи заявки"""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("💼 Есть ли у вас опыт в этой сфере? (Да/Нет)")
    return EXPERIENCE

async def receive_experience(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Получение информации об опыте"""
    context.user_data['experience'] = update.message.text[:200]  # Ограничение длины
    await update.message.reply_text("⏳ Сколько часов в день вы готовы уделять работе? (Цифра)")
    return TIME

async def receive_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Получение информации о времени"""
    try:
        hours = float(update.message.text.replace(',', '.'))
        if hours <= 0 or hours > 24:
            await update.message.reply_text("⚠ Пожалуйста, введите корректное число часов (0-24)")
            return TIME
        context.user_data['time'] = f"{hours:.1f} ч/день"
    except ValueError:
        await update.message.reply_text("⚠ Пожалуйста, введите число")
        return TIME
    
    await update.message.reply_text("🎯 Расскажите, почему вы хотите присоединиться?")
    return MOTIVATION

async def receive_motivation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Завершение заявки и отправка администраторам"""
    user = update.effective_user
    context.user_data['motivation'] = update.message.text[:500]  # Ограничение длины
    
    # Формируем текст заявки с экранированием Markdown
    try:
        application_text = (
            "📌 *Новая заявка*\n\n"
            f"👤 *Имя:* {escape_markdown(user.full_name, version=2)}\n"
            f"📱 *Username:* @{escape_markdown(user.username, version=2) if user.username else 'нет'}\n"
            f"🆔 *ID:* `{user.id}`\n\n"
            f"💼 *Опыт:* {escape_markdown(context.user_data['experience'], version=2)}\n"
            f"⏳ *Время:* {escape_markdown(context.user_data['time'], version=2)}\n"
            f"🎯 *Мотивация:* {escape_markdown(context.user_data['motivation'], version=2)}"
        )
        
        keyboard = [
            [
                InlineKeyboardButton("✅ Одобрить", callback_data=f"approve_{user.id}"),
                InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{user.id}")
            ]
        ]
        
        # Отправляем всем админам с MarkdownV2
        for admin_id in ADMIN_IDS:
            try:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=application_text,
                    parse_mode="MarkdownV2",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            except Exception as e:
                logger.error(f"MarkdownV2 ошибка для {admin_id}: {e}")
                # Отправка без форматирования, если Markdown не работает
                plain_text = (
                    "📌 Новая заявка\n\n"
                    f"👤 Имя: {user.full_name}\n"
                    f"📱 Username: @{user.username if user.username else 'нет'}\n"
                    f"🆔 ID: {user.id}\n\n"
                    f"💼 Опыт: {context.user_data['experience']}\n"
                    f"⏳ Время: {context.user_data['time']}\n"
                    f"🎯 Мотивация: {context.user_data['motivation']}"
                )
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=plain_text,
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
                
    except Exception as e:
        logger.error(f"Критическая ошибка при отправке: {e}")
        await update.message.reply_text("⚠ Произошла ошибка при отправке заявки")

    await update.message.reply_text("✅ Ваша заявка отправлена! Ожидайте ответа.")
    return ConversationHandler.END

async def admin_decision(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработка решения администратора"""
    query = update.callback_query
    await query.answer()
    
    if not is_admin(query.from_user.id):
        await query.edit_message_text("⚠ Доступ запрещён")
        return
    
    action, user_id = query.data.split('_')
    response = "🎉 Ваша заявка одобрена! Скоро с вами свяжутся." if action == "approve" else "😕 Ваша заявка отклонена."
    
    try:
        await context.bot.send_message(chat_id=user_id, text=response)
        await query.edit_message_reply_markup()  # Удаляем кнопки
    except Exception as e:
        logger.error(f"Ошибка при обработке решения: {e}")
        await query.answer("⚠ Произошла ошибка")

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отмена подачи заявки"""
    await update.message.reply_text("❌ Подача заявки отменена. Напишите /start чтобы начать заново.")
    return ConversationHandler.END

async def toggle_bot(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Включение/выключение бота (для админов)"""
    global BOT_ACTIVE
    
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⚠ Эта команда только для администраторов")
        return
    
    BOT_ACTIVE = not BOT_ACTIVE
    status = "включён" if BOT_ACTIVE else "выключен"
    await update.message.reply_text(f"🔄 Бот {status}")

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Глобальный обработчик ошибок"""
    logger.error("Ошибка в обработчике", exc_info=context.error)
    if update and isinstance(update, Update):
        try:
            await update.message.reply_text("⚠ Произошла ошибка. Попробуйте позже.")
        except:
            try:
                await update.callback_query.message.reply_text("⚠ Произошла ошибка. Попробуйте позже.")
            except:
                pass

def main() -> None:
    """Запуск бота"""
    app = Application.builder().token(TOKEN).build()
    
    # Настройка ConversationHandler
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler('start', start),
            CallbackQueryHandler(start_application, pattern="^start_application$")
        ],
        states={
            EXPERIENCE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_experience)],
            TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_time)],
            MOTIVATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_motivation)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        allow_reentry=True
    )
    
    # Регистрация обработчиков
    app.add_handler(conv_handler)
    app.add_handler(CallbackQueryHandler(admin_decision, pattern=r"^(approve|reject)_\d+$"))
    app.add_handler(CommandHandler('toggle', toggle_bot))
    app.add_error_handler(error_handler)
    
    # Настройки для Render
    app.run_polling(
        drop_pending_updates=True,
        poll_interval=3.0,
        close_loop=False,
        stop_signals=[]
    )

if __name__ == '__main__':
    main()
