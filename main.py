import logging
import os
import re
import asyncio

from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ConversationHandler, filters, ContextTypes
from pyrogram import Client
from pyrogram.enums import ParseMode

# Добавленные импорты
from database import Database
from admin_handlers import admin_command, admin_teams_list, handle_team_action, admin_teams_menu, process_comment, cancel_comment, admin_panel, admin_teams_list_pending, admin_teams_list_approved, admin_teams_list_rejected, WAITING_FOR_COMMENT
from registration_status import check_registration_status


# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
API_ID = int(os.environ.get("API_ID"))
API_HASH = os.environ.get("API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN")

# Define states
(
    CHECKING_SUBSCRIPTION,
    TEAM_NAME,
    CAPTAIN_NICKNAME,
    PLAYERS_LIST,
    SUBSCRIPTION_CHECK_RESULT,
    CAPTAIN_CONTACTS,
    TOURNAMENT_INFO,
    FAQ,
    WAITING_TEAM_NAME,
    WAITING_FOR_COMMENT,
    WAITING_FOR_ADMIN_ID  # Add this new state
) = range(11)  # Изменено на range(10)

# Channel ID for subscription check
CHANNEL_ID = "@m5cup"

# Pyrogram Client (UserBot)
userbot = Client(
    name="my_userbot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    parse_mode=ParseMode.HTML
)

# Инициализация базы данных
db = Database()

# Клавиатуры
def get_main_keyboard():
    """Главная клавиатура с основными функциями."""
    keyboard = [
        [KeyboardButton("Регистрация")],
        [KeyboardButton("Информация о турнире")],
        [KeyboardButton("Проверить статус регистрации")],
        [KeyboardButton("FAQ")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_registration_keyboard():
    """Клавиатура для этапа регистрации."""
    keyboard = [
        [KeyboardButton("Проверить подписку")],
        [KeyboardButton("Назад")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_back_keyboard():
    """Простая клавиатура только с кнопкой Назад."""
    keyboard = [
        [KeyboardButton("Назад")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_subscription_result_keyboard():
    """Клавиатура для результата проверки подписки."""
    keyboard = [
        [KeyboardButton("Продолжить")],
        [KeyboardButton("Назад")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_confirmation_keyboard():
    """Клавиатура для подтверждения списка игроков."""
    keyboard = [
        [KeyboardButton("✅ Продолжить")],
        [KeyboardButton("🔄 Отправить список заново")],
        [KeyboardButton("Назад")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Send welcome message and show main menu."""
    welcome_message = """🏆 Добро пожаловать в бота регистрации на турнир

"M5 Domination Cup"


Я помогу вам зарегистрироваться на турнир и предоставлю всю необходимую информацию.


📝 Что я умею:
• Регистрация команды на турнир
• Просмотр информации о турнире
• Проверка статуса регистрации
• Ответы на часто задаваемые вопросы


🎮 Для начала регистрации нажмите кнопку "Регистрация" ниже.
ℹ️ Для получения дополнительной информации выберите "Информация о турнире".


Важно: Убедитесь, что у вас готова следующая информация:
• Название команды
• Список игроков (никнеймы)
• Контактные данные капитана (Дискорд или телеграм)


Удачи в турнире! 🎯"""

    await update.message.reply_text(welcome_message, reply_markup=get_main_keyboard())
    return ConversationHandler.END

async def start_registration(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start the registration process."""
    await update.message.reply_text(
        "📢 Для участия в M5 Domination Cup необходимо быть подписанным на наш канал!\n\n"
        "🔗 Подпишись на [M5 Cup](https://t.me/m5cup), затем нажми \"Проверить подписку\".\n\n"
        "🛑 Если ты уже подписан, просто нажми \"Проверить подписку\".",
        reply_markup=get_registration_keyboard(),
        parse_mode='Markdown'
    )
    return CHECKING_SUBSCRIPTION

async def back_to_main(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Return to main menu."""
    await update.message.reply_text(
        "Вы вернулись в главное меню. Выберите нужное действие:",
        reply_markup=get_main_keyboard()
    )
    return ConversationHandler.END

async def back_to_checking_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Return to subscription checking step."""
    await update.message.reply_text(
        "📢 Для участия в M5 Domination Cup необходимо быть подписанным на наш канал!\n\n"
        "🔗 Подпишись на [M5 Cup](https://t.me/m5cup), затем нажми \"Проверить подписку\".\n\n"
        "🛑 Если ты уже подписан, просто нажми \"Проверить подписку\".",
        reply_markup=get_registration_keyboard(),
        parse_mode='Markdown'
    )
    return CHECKING_SUBSCRIPTION

async def back_to_team_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Return to team name input step."""
    await update.message.reply_text(
        "🎮 Введи название твоей команды.\n\n"
        "✍🏼 Напиши название в ответном сообщении.",
        reply_markup=get_back_keyboard()
    )
    return TEAM_NAME

async def back_to_players_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Return to players list input step."""
    await update.message.reply_text(
        "Укажи состав команды. Тебе нужно указать:\n"
        "1️⃣ 4 основных игрока\n"
        "2️⃣ Запасных игроков (если есть)\n\n"
        "⚠️ Формат:\n"
        "📌 Игровой никнейм – @TelegramUsername\n\n"
        "👀 Пример:\n\n"
        "PlayerOne – @playerone\n"
        "PlayerTwo – @playertwo\n"
        "PlayerThree – @playerthree\n"
        "PlayerFour – @playerfour\n"
        "(5. Запасной – @reserveplayer)\n\n"
        "📩 Отправь список в ответном сообщении.",
        reply_markup=get_back_keyboard()
    )
    return PLAYERS_LIST

async def check_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Check if user is subscribed to the channel."""
    try:
        user_id = update.message.from_user.id
        chat_member = await context.bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)

        if chat_member.status in ['member', 'administrator', 'creator']:
            await update.message.reply_text(
                "🎮 Отлично! Теперь введи название твоей команды.\n\n"
                "✍🏼 Напиши название в ответном сообщении.",
                reply_markup=get_back_keyboard()
            )
            return TEAM_NAME
        else:
            await update.message.reply_text(
                "❌ Вы не подписаны на канал. Пожалуйста, подпишитесь на @m5cup и попробуйте снова.",
                reply_markup=get_registration_keyboard()
            )
            return CHECKING_SUBSCRIPTION

    except Exception as e:
        logger.error(f"Error checking subscription: {e}")
        await update.message.reply_text(
            "❌ Произошла ошибка при проверке подписки. Пожалуйста, убедитесь, что вы:\n\n"
            "1. Перешли по ссылке в канал\n"
            "2. Подписались на канал\n"
            "3. Нажали кнопку \"Проверить подписку\"\n\n"
            "Если проблема сохраняется, попробуйте позже.",
            reply_markup=get_registration_keyboard()
        )
        return CHECKING_SUBSCRIPTION

async def receive_team_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receive and store team name, check for uniqueness, and proceed to captain nickname."""
    team_name = update.message.text

    # Проверяем, существует ли команда с таким именем (без учета регистра)
    if db.team_name_exists(team_name):
        await update.message.reply_text(
            "⚠️ Команда с таким названием уже зарегистрирована. Пожалуйста, выберите другое название.",
            reply_markup=get_back_keyboard()  # Or other appropriate keyboard
        )
        return TEAM_NAME  # Return to team name input state

    context.user_data['team_name'] = team_name

    await update.message.reply_text(
        "Теперь введи свой игровой никнейм (это будет твой никнейм в игре, и ты будешь капитаном команды):\n\n"
        "✍🏼 Напиши никнейм в ответном сообщении.",
        reply_markup=get_back_keyboard()
    )
    return CAPTAIN_NICKNAME

async def get_tg_id_by_username(username: str):
    """Gets Telegram ID by username using Pyrogram."""
    try:
        users = await userbot.get_users(username)
        if users:
            if isinstance(users, list):
                if users:
                    return users[0].id
                else:
                    return None
            else:
                return users.id
        else:
            return None
    except Exception as e:
        logger.error(f"Error getting Telegram ID for {username}: {e}")
        return None
    
async def receive_captain_nickname(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receive captain's nickname and proceed to player list."""
    captain_nickname = update.message.text
    context.user_data['captain_nickname'] = captain_nickname

    await update.message.reply_text(
        "Теперь укажи состав команды (минимум 3 игрока, не включая капитана):\n\n"
        "⚠️ Формат:\n"
        "📌 Игровой никнейм – @TelegramUsername\n\n"
        "👀 Пример:\n\n"
        "PlayerOne – @playerone\n"
        "PlayerTwo – @playertwo\n"
        "PlayerThree – @playerthree\n"
        "(4. Запасной – @reserveplayer)\n\n"
        "📩 Отправь список в ответном сообщении.",
        reply_markup=get_back_keyboard()
    )
    return PLAYERS_LIST

async def check_players_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Check and validate players list and check subscription status."""
    players_text = update.message.text
    players = []
    player_pattern = re.compile(r"(.+?)\s*[-–]\s*@([a-zA-Z0-9_]+)")

    for line in players_text.split('\n'):
        match = player_pattern.match(line)
        if match:
            nickname = match.group(1).strip()
            username = match.group(2).strip()
            players.append((nickname, username))

    if len(players) < 3:
        await update.message.reply_text(
            "⚠️ Необходимо указать минимум 3 игрока (не включая капитана). Пожалуйста, проверьте формат и количество игроков и отправьте список снова.",
            reply_markup=get_back_keyboard()
        )
        return PLAYERS_LIST

    # Словарь для хранения информации об игроках (nickname, username, telegram_id)
    players_data = []
    # Добавляем капитана в список players_data
    captain_nickname = context.user_data.get('captain_nickname')
    update_user = update.message.from_user
    players_data.append({"nickname": captain_nickname, "username": update_user.username, "telegram_id": update_user.id, 'is_captain': True})
    for nickname, username in players:
        players_data.append({"nickname": nickname, "username": username, "telegram_id": None, 'is_captain': False})
    
    # Проверяем на уникальность никнеймов и юзернеймов
    nicknames = set()
    usernames = set()
    duplicate_nicknames = []
    duplicate_usernames = []

    for player in players_data:
        if player['nickname'] in nicknames:
            duplicate_nicknames.append(player['nickname'])
        else:
            nicknames.add(player['nickname'])

        # Приводим юзернейм к нижнему регистру перед проверкой
        username_lower = player['username'].lower()
        if username_lower in usernames:
            duplicate_usernames.append(player['username'])
        else:
            usernames.add(username_lower)
    
    if duplicate_nicknames or duplicate_usernames:
        error_message = "⚠️ Обнаружены дубликаты:\n"
        if duplicate_nicknames:
            error_message += f"Повторяющиеся никнеймы: {', '.join(duplicate_nicknames)}\n"
        if duplicate_usernames:
            error_message += f"Повторяющиеся юзернеймы: {', '.join(duplicate_usernames)}\n"
        
        error_message += "Пожалуйста, исправьте список игроков и отправьте его снова."
        
        await update.message.reply_text(
            error_message,
            reply_markup=get_back_keyboard()
        )
        return PLAYERS_LIST

    context.user_data['players_data'] = players_data

    await update.message.reply_text(
        "⏳ Проверяем подписку игроков на канал. Это может занять некоторое время...",
        reply_markup=ReplyKeyboardRemove()
    )

    unsubscribed_players = []
    subscribed_players = []

    for i, player in enumerate(players_data): # Добавляем индекс
        if player['telegram_id'] is None:
            telegram_id = await get_tg_id_by_username(player['username'])
            player['telegram_id'] = telegram_id
        else:
            telegram_id = player['telegram_id']
        if telegram_id:
            try:
                chat_member = await context.bot.get_chat_member(chat_id=CHANNEL_ID, user_id=telegram_id)
                if chat_member.status in ['member', 'administrator', 'creator']:
                    subscribed_players.append(f"{player['nickname']} – @{player['username']}")
                else:
                    unsubscribed_players.append(f"{player['nickname']} – @{player['username']}")
            except Exception as e:
                logger.error(f"Error checking subscription for user {telegram_id} (Bot API): {e}")
                if "Participant_id_invalid" in str(e):
                    unsubscribed_players.append(f"{player['nickname']} – @{player['username']} (Ошибка проверки)")
                else:
                    unsubscribed_players.append(f"{player['nickname']} – @{player['username']} (Ошибка проверки)")


        else:
            unsubscribed_players.append(f"{player['nickname']} – @{player['username']} (Проверьте правильность юзернейма)")

    if unsubscribed_players:
        message = "⚠️ Следующие игроки не подписаны на канал @m5cup или не удалось проверить их подписку:\n"
        for player in unsubscribed_players:
            message += f"• {player}\n"
        message += "\nПожалуйста, убедитесь, что все игроки подписаны на канал. Некоторые проверки могли не пройти из-за настроек приватности пользователя"
    else:
        message = "✅ Все игроки из списка подписаны на канал @m5cup!"

    # Сохраняем сообщение для повторного использования
    context.user_data['subscription_message'] = message
    # Сохраняем информацию об игроках, включая telegram_id
    # Обновляем информацию об игроках в context.user_data (после получения telegram_id)
    context.user_data['players_data'] = players_data

    await update.message.reply_text(message, reply_markup=get_subscription_result_keyboard())
    return SUBSCRIPTION_CHECK_RESULT

async def handle_subscription_result(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle user's choice after subscription check."""
    choice = update.message.text

    if choice == "Продолжить":
        await update.message.reply_text(
            "📞 Теперь укажи контакты капитана команды.\n\n"
            "💬 Напиши в ответном сообщении Telegram или Discord капитана.\n\n"
            "👀 Пример:\n"
            "📌 Telegram: @CaptainUsername\n"
            "или\n"
            "📌 Discord: Captain#1234",
            reply_markup=get_back_keyboard()
        )
        return CAPTAIN_CONTACTS
    elif choice == "Назад":
        await update.message.reply_text(
            "Пожалуйста, отправьте список игроков заново.",
            reply_markup=get_back_keyboard()
        )
        return PLAYERS_LIST
    else:
        # Handle unexpected input (optional)
        await update.message.reply_text(
            "Неизвестный ввод. Пожалуйста, используйте кнопки.",
            reply_markup=get_subscription_result_keyboard()
        )
        return SUBSCRIPTION_CHECK_RESULT

async def handle_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle player list confirmation."""
    user_choice = update.message.text
    
    if user_choice == "✅ Продолжить":
        await update.message.reply_text(
            "📞 Теперь укажи контакты капитана команды.\n\n"
            "💬 Напиши в ответном сообщении Telegram или Discord капитана.\n\n"
            "👀 Пример:\n"
            "📌 Telegram: @CaptainUsername\n"
            "или\n"
            "📌 Discord: Captain#1234",
            reply_markup=get_back_keyboard()
        )
        return CAPTAIN_CONTACTS
    
    elif user_choice == "🔄 Отправить список заново":
        await update.message.reply_text(
            "🔄 Пожалуйста, отправьте список игроков заново в формате:\n\n"
            "PlayerOne – @playerone\n"
            "PlayerTwo – @playertwo\n"
            "PlayerThree – @playerthree\n"
            "PlayerFour – @playerfour\n"
            "(5. Запасной – @reserveplayer)",
            reply_markup=get_back_keyboard()
        )
        return PLAYERS_LIST
    
    elif user_choice == "Назад":
        return await back_to_players_list(update, context)

async def finish_registration(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Complete the registration process."""
    captain_contact = update.message.text
    context.user_data['captain_contact'] = captain_contact

    team_name = context.user_data.get('team_name', 'Не указано')
    players_data = context.user_data.get('players_data', [])

    try:
        team_id = db.register_team(
            team_name=team_name,
            players=players_data,
            captain_contact=captain_contact
        )
        logger.info(f"Team '{team_name}' registered successfully with ID: {team_id}")

    except Exception as e:
        logger.error(f"Error saving team data to database: {e}")
        await update.message.reply_text(
            "❌ Произошла ошибка при сохранении данных в базу данных. Пожалуйста, попробуйте позже.",
            reply_markup=get_main_keyboard()
        )
        return ConversationHandler.END

    registration_info = (
        f"✅ Поздравляем! Ваша команда успешно зарегистрирована на M5 Domination Cup!\n\n"
        f"📋 Информация о регистрации:\n"
        f"🎮 Название команды: {team_name}\n\n"
        f"👥 Состав команды:\n"
    )

    for player in players_data:
        registration_info += f"  - 🎮 {player['nickname']} (@{player['username']}) {'(Капитан)' if player['is_captain'] else ''}\n"

    registration_info += f"\n👨‍✈️ Контакты капитана: {captain_contact}\n\n"
    registration_info += "📢 Вскоре мы свяжемся с капитаном для подтверждения участия.\n\n"
    registration_info += "🔥 Удачи в турнире! 🎮🏆"

    await update.message.reply_text(registration_info, reply_markup=get_main_keyboard())
    return ConversationHandler.END

async def tournament_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Show tournament information."""
    await update.message.reply_text(
        "🏆 M5 Domination Cup\n\n"
        "📅 Информация о турнире будет добавлена позже.",
        reply_markup=get_back_keyboard()
    )
    return TOURNAMENT_INFO

# async def registration_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
#     """Check registration status."""
#     await update.message.reply_text(
#         "🔍 Функция проверки статуса регистрации будет доступна позже.",
#         reply_markup=get_back_keyboard()
#     )
#     return REGISTRATION_STATUS

async def faq(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Show FAQ."""
    await update.message.reply_text(
        "❓ Часто задаваемые вопросы:\n\n"
        "Информация будет добавлена позже.",
        reply_markup=get_back_keyboard()
    )
    return FAQ

async def post_init(application: Application):
    """Post initialization hook to start the Pyrogram client."""
    print("Starting Pyrogram client...")
    await userbot.start()
    print("Pyrogram client started.")

async def admin_add_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle adding a new admin."""
    query = update.callback_query
    await query.answer()
    await query.message.reply_text(
        "👤 Введите Telegram ID нового администратора:",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("Отмена", callback_data="admin_panel")
        ]])
    )
    return WAITING_FOR_ADMIN_ID

async def process_new_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process new admin ID input."""
    admin_id = update.message.text.strip()

    try:
        admin_id = int(admin_id)

        # Check if user is a bot
        user = await context.bot.get_chat(admin_id)
        if user.type == "private" and user.is_bot:
            await update.message.reply_text(
                "❌ Нельзя добавить бота в качестве администратора.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("Вернуться в панель", callback_data="admin_panel")
                ]])
            )
            return ConversationHandler.WAITING

        # Add to database
        if db.add_admin(admin_id):
            await update.message.reply_text(
                f"✅ Администратор с ID {admin_id} успешно добавлен.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("Вернуться в панель", callback_data="admin_panel")
                ]])
            )
        else:
            await update.message.reply_text(
                f"⚠️ Пользователь с ID {admin_id} уже является администратором.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("Вернуться в панель", callback_data="admin_panel")
                ]])
            )
    except ValueError:
        await update.message.reply_text(
            "❌ Некорректный ID. Введите числовой Telegram ID.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("Вернуться в панель", callback_data="admin_panel")
            ]])
        )
    except Exception as e:
        logger.error(f"Error adding admin with ID {admin_id}: {e}")
        await update.message.reply_text(
            f"❌ Произошла ошибка при добавлении администратора.  Попробуйте позже.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("Вернуться в панель", callback_data="admin_panel")
            ]])
        )

    return ConversationHandler.WAITING

async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show detailed registration statistics."""
    query = update.callback_query
    await query.answer()

    # Get statistics from database
    stats = db.get_stats()

    # Format status counts
    status_counts = stats['teams_by_status']
    pending_count = status_counts.get('pending', 0)
    approved_count = status_counts.get('approved', 0)
    rejected_count = status_counts.get('rejected', 0)

    # Format recent registrations
    recent_reg_text = "\n".join([
        f"• {reg['team_name']} ({reg['date']})"
        for reg in stats['recent_registrations']
    ]) if stats['recent_registrations'] else "Нет данных"

    # Players by status
    players_status = stats['players_by_status']
    pending_players = players_status.get('pending', 0)
    approved_players = players_status.get('approved', 0)
    rejected_players = players_status.get('rejected', 0)

    stats_text = (
        "📊 Подробная статистика регистраций:\n\n"
        f"👥 Команды:\n"
        f"  • 🔄 Ожидают проверки: {pending_count}\n"
        f"  • ✅ Одобрено: {approved_count}\n"
        f"  • ❌ Отклонено: {rejected_count}\n"
        f"  • 📝 Всего команд: {stats['total_teams']}\n\n"

        f"🎮 Игроки:\n"
        f"  • 👤 Всего игроков: {stats['total_players']}\n"
        f"  • 📊 Среднее кол-во в команде: {stats['avg_players_per_team']:.1f}\n"
        f"  • 🔄 В ожидающих командах: {pending_players}\n"
        f"  • ✅ В одобренных командах: {approved_players}\n"
        f"  • ❌ В отклоненных командах: {rejected_players}\n\n"

        f"🆕 Последние регистрации:\n{recent_reg_text}\n\n"

        f"👮 Администраторов в системе: {stats['admin_count']}"
    )

    await query.message.edit_text(
        stats_text,
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("Назад", callback_data="admin_panel")
        ]]),
        parse_mode='Markdown'
    )

    return ConversationHandler.WAITING

def main() -> None:
    """Start the bot."""
    application = Application.builder().token(BOT_TOKEN).post_init(post_init).build()

    # Добавляем базу данных в bot_data, чтобы она была доступна в обработчиках
    application.bot_data['db'] = db

    # Добавляем обработчики админ-панели
    admin_conv_handler = ConversationHandler(
    entry_points=[CommandHandler("admin", admin_command)],
    states={
        WAITING_FOR_COMMENT: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, process_comment),
            CallbackQueryHandler(cancel_comment, pattern="^cancel_comment$")
        ],
        WAITING_FOR_ADMIN_ID: [  # Добавляем новое состояние для обработки ввода ID админа
            MessageHandler(filters.TEXT & ~filters.COMMAND, process_new_admin),
        ],
        # Используем WAITING вместо END для обработки меню и действий с командами
        ConversationHandler.WAITING: [
            CallbackQueryHandler(admin_teams_menu, pattern="^admin_teams_menu$"),
            CallbackQueryHandler(admin_teams_list_pending, pattern="^admin_teams_list_pending$"),
            CallbackQueryHandler(admin_teams_list_approved, pattern="^admin_teams_list_approved$"),
            CallbackQueryHandler(admin_teams_list_rejected, pattern="^admin_teams_list_rejected$"),
            CallbackQueryHandler(admin_add_admin, pattern="^admin_add_admin$"),  # Добавляем обработчик для "Добавить админа"
            CallbackQueryHandler(admin_stats, pattern="^admin_stats$"),  # Добавляем обработчик для "Статистика"
            CallbackQueryHandler(handle_team_action, pattern="^(approve|reject|comment)_team_"),
            CallbackQueryHandler(admin_panel, pattern="^admin_panel$"),
        ],
    },
    fallbacks=[CommandHandler("admin", admin_command)],
    map_to_parent={
        ConversationHandler.END: ConversationHandler.END,
        ConversationHandler.WAITING: ConversationHandler.WAITING,
        WAITING_FOR_ADMIN_ID: ConversationHandler.WAITING
    }
)

    application.add_handler(admin_conv_handler)

    # Обновляем ConversationHandler для регистрации пользователей
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler('start', start),
            MessageHandler(filters.Regex('^Регистрация$'), start_registration),
            MessageHandler(filters.Regex('^Информация о турнире$'), tournament_info),
            MessageHandler(filters.Regex('^Проверить статус регистрации$'), check_registration_status),  # Use the function directly
            MessageHandler(filters.Regex('^FAQ$'), faq),
        ],
        states={
            CHECKING_SUBSCRIPTION: [
                MessageHandler(filters.Regex('^Проверить подписку$'), check_subscription),
                MessageHandler(filters.Regex('^Назад$'), back_to_main),
            ],
            TEAM_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex('^Назад$'), receive_team_name),
                MessageHandler(filters.Regex('^Назад$'), back_to_checking_subscription),
            ],
            CAPTAIN_NICKNAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex('^Назад$'), receive_captain_nickname),
                MessageHandler(filters.Regex('^Назад$'), back_to_team_name),
            ],
            PLAYERS_LIST: [
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex('^Назад$'), check_players_subscription),
                MessageHandler(filters.Regex('^Назад$'), back_to_team_name),
            ],
            SUBSCRIPTION_CHECK_RESULT: [
                MessageHandler(filters.Regex('^Продолжить$|^Назад$'), handle_subscription_result),
            ],
            CAPTAIN_CONTACTS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex('^Назад$'), finish_registration),
                MessageHandler(filters.Regex('^Назад$'), back_to_players_list),
            ],
            TOURNAMENT_INFO: [
                MessageHandler(filters.Regex('^Назад$'), back_to_main),
            ],
            FAQ: [
                MessageHandler(filters.Regex('^Назад$'), back_to_main),
            ],
        },
        fallbacks=[CommandHandler('start', start)],
    )

    application.add_handler(conv_handler)

    # Start the Bot
    application.run_polling()

    # Остановка Pyrogram клиента при выходе
    asyncio.run(userbot.stop())

if __name__ == '__main__':
    main()
