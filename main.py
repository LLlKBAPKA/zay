import os
import logging
import asyncio
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
ADMIN_CHAT_IDS = [int(id) for id in os.getenv("ADMIN_IDS", "").split(",") if id]

# Этапы диалога
START, EXPERIENCE, TIME_PER_DAY, MOTIVATION = range(4)

class BotApplication:
    def __init__(self):
        self.app = Application.builder().token(TOKEN).build()
        self._setup_handlers()
        self.restart_count = 0
        self.max_restarts = 3

    def _setup_handlers(self):
        conv_handler = ConversationHandler(
            entry_points=[
                CommandHandler('start', self._start),
                CallbackQueryHandler(self._apply, pattern="^apply$")
            ],
            states={
                EXPERIENCE: [MessageHandler(filters.TEXT & ~filters.COMMAND, self._experience)],
                TIME_PER_DAY: [MessageHandler(filters.TEXT & ~filters.COMMAND, self._time_per_day)],
                MOTIVATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, self._motivation)],
            },
            fallbacks=[CommandHandler('cancel', self._cancel)],
            per_message=True
        )

        self.app.add_handler(conv_handler)
        self.app.add_handler(CallbackQueryHandler(self._admin_action, pattern=r"^(accept|reject)_\d+$"))
        self.app.add_handler(CommandHandler('cancel', self._cancel))
        self.app.add_error_handler(self._error_handler)

    async def _start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        keyboard = [[InlineKeyboardButton("Подать заявку", callback_data="apply")]]
        await update.message.reply_text(
            "🚀 Привет! Это бот для подачи заявок в нашу команду.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return START

    async def _apply(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query
        await query.answer()
        await query.edit_message_text("💼 Был ли у вас опыт в этой сфере? (Да/Нет)")
        return EXPERIENCE

    async def _experience(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        context.user_data['experience'] = update.message.text[:100]
        await update.message.reply_text("⏳ Сколько часов в день готовы уделять работе? (Цифра)")
        return TIME_PER_DAY

    async def _time_per_day(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        try:
            hours = float(update.message.text.replace(',', '.'))
            context.user_data['time_per_day'] = f"{hours} ч."
        except ValueError:
            context.user_data['time_per_day'] = update.message.text[:50]
        
        await update.message.reply_text("🎯 Что хотите получить от работы? (Кратко)")
        return MOTIVATION

    async def _motivation(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        context.user_data['motivation'] = update.message.text[:300]
        user = update.effective_user

        application_text = (
            "📌 *Новая заявка*\n\n"
            f"👤 *Пользователь:* @{user.username or 'нет'}\n"
            f"🆔 *ID:* `{user.id}`\n"
            f"📝 *Имя:* {user.full_name}\n\n"
            f"💼 *Опыт:* {context.user_data.get('experience', 'не указано')}\n"
            f"⏳ *Время в день:* {context.user_data.get('time_per_day', 'не указано')}\n"
            f"🎯 *Цель:* {context.user_data.get('motivation', 'не указано')}"
        )

        for admin_id in ADMIN_CHAT_IDS:
            try:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=application_text,
                    parse_mode="Markdown",
                    reply_markup=self._get_admin_keyboard(user.id)
                )
            except Exception as e:
                logger.error(f"Ошибка отправки админу {admin_id}: {e}")

        await update.message.reply_text("✅ Заявка отправлена! Ожидайте ответа.")
        return ConversationHandler.END

    def _get_admin_keyboard(self, applicant_id: int) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Принять", callback_data=f"accept_{applicant_id}"),
                InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{applicant_id}")
            ]
        ])

    async def _admin_action(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        await query.answer()
        
        try:
            action, user_id = query.data.split('_')
            user_id = int(user_id)
            
            response_text = "🎉 Ваша заявка одобрена! С вами свяжутся." if action == "accept" else "😕 Ваша заявка отклонена."
            await context.bot.send_message(chat_id=user_id, text=response_text)
            await query.edit_message_reply_markup()
            
        except Exception as e:
            logger.error(f"Ошибка обработки действия админа: {e}")
            await query.answer("Произошла ошибка")

    async def _cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        await update.message.reply_text("Диалог прерван. Напишите /start чтобы начать заново.")
        return ConversationHandler.END

    async def _error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        logger.error("Ошибка в обработчике", exc_info=context.error)

    async def run(self):
        while self.restart_count < self.max_restarts:
            try:
                await self.app.initialize()
                await self.app.start()
                await self.app.updater.start_polling(
                    poll_interval=3.0,
                    drop_pending_updates=True,
                    timeout=20
                )
                await self.app.updater.idle()
            except Exception as e:
                self.restart_count += 1
                logger.error(f"Ошибка (попытка {self.restart_count}/{self.max_restarts}): {e}")
                await asyncio.sleep(5)
            finally:
                await self.app.stop()
                await self.app.shutdown()

        logger.error("Достигнуто максимальное количество перезапусков. Бот остановлен.")

if __name__ == '__main__':
    bot = BotApplication()
    asyncio.run(bot.run())
