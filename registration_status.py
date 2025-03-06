# registration_status.py
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

async def check_registration_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Check registration status by user's Telegram ID."""
    telegram_id = update.message.from_user.id

    team = context.bot_data['db'].get_team_by_telegram_id(telegram_id)

    if team:
        # Переводим статус на русский язык
        status_translation = {
            "pending": "Ожидает подтверждения",
            "approved": "Одобрено",
            "rejected": "Отклонено",
        }
        status = status_translation.get(team['status'], "Неизвестно")  # Fallback

        message = (
            f"<b>Статус регистрации команды:</b>\n"
            f"🏆 Название команды: {team['team_name']}\n"
            f"✅ Статус: {status}\n"
            f"👥 Игроки:\n"
        )
        for player in team['players']:
            message += f"  - 🎮 {player[0]} (@{player[1]})\n"
    else:
        message = "⚠️ Вы еще не зарегистрировали свою команду или вас еще не зарегистрировали для участия в турнире."

    await update.message.reply_text(message, parse_mode='HTML')
    return ConversationHandler.END  # Exit conversation
