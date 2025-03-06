from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler, ConversationHandler, MessageHandler, filters
from database import Database

db = Database()

# Добавляем состояния для ожидания данных
WAITING_FOR_COMMENT = 1
WAITING_FOR_ADMIN_ID = 2

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Показать админ-панель."""
    if not db.is_admin(update.effective_user.id):
        await update.message.reply_text("У вас нет доступа к админ-панели.")
        return ConversationHandler.END  # Завершаем для неадминов

    keyboard = [
        [InlineKeyboardButton("📋 Список команд", callback_data="admin_teams_menu")],
        [InlineKeyboardButton("➕ Добавить админа", callback_data="admin_add_admin")],
        [InlineKeyboardButton("📊 Статистика", callback_data="admin_stats")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "🔐 Админ-панель\n\nВыберите действие:",
        reply_markup=reply_markup
    )
    # Возвращаем WAITING вместо None
    return ConversationHandler.WAITING

async def admin_teams_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показать меню выбора статуса команд."""
    query = update.callback_query
    if not db.is_admin(query.from_user.id):
        await query.answer("У вас нет доступа к этой функции.")
        return ConversationHandler.END

    pending_count = db.get_teams_count_by_status("pending")
    approved_count = db.get_teams_count_by_status("approved")
    rejected_count = db.get_teams_count_by_status("rejected")

    keyboard = [
        [InlineKeyboardButton(f"Ожидающие команды - {pending_count}", callback_data="admin_teams_list_pending")] if pending_count > 0 else [InlineKeyboardButton("Ожидающие команды", callback_data="admin_teams_list_pending")],
        [InlineKeyboardButton(f"Подтвержденные команды - {approved_count}", callback_data="admin_teams_list_approved")] if approved_count > 0 else [InlineKeyboardButton("Подтвержденные команды", callback_data="admin_teams_list_approved")],
        [InlineKeyboardButton(f"Отклоненные команды - {rejected_count}", callback_data="admin_teams_list_rejected")] if rejected_count > 0 else [InlineKeyboardButton("Отклоненные команды", callback_data="admin_teams_list_rejected")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="admin_panel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text("Выберите статус команд для просмотра:", reply_markup=reply_markup)
    await query.answer()

    # Возвращаем WAITING
    return ConversationHandler.WAITING

async def admin_teams_list(update: Update, context: ContextTypes.DEFAULT_TYPE, status: str) -> None:
    """Показать список команд с определенным статусом."""
    query = update.callback_query
    if not db.is_admin(query.from_user.id):
        await query.answer("У вас нет доступа к этой функции.")
        return

    teams = db.get_all_teams_by_status(status)

    if not teams:
        await query.edit_message_text(
            f"Нет команд со статусом '{status}'.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data="admin_teams_menu")]])
        )
        return

    for team in teams:
        keyboard = [
            [
                InlineKeyboardButton("✅ Одобрить", callback_data=f"approve_team_{team['id']}"),
                InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_team_{team['id']}")
            ],
            [InlineKeyboardButton("💬 Комментарий", callback_data=f"comment_team_{team['id']}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        players_list = "\n".join([f"• {p[0]} – {p[1]}" for p in team['players']])
        message = (
            f"🎮 Команда: {team['team_name']}\n"
            f"📅 Дата регистрации: {team['registration_date']}\n"
            f"📱 Контакт капитана: {team['captain_contact']}\n"
            f"📊 Статус: {team['status']}\n"
            f"💭 Комментарий: {team['admin_comment'] or 'Нет'}\n\n"
            f"👥 Игроки:\n{players_list}"
        )

        await query.message.reply_text(message, reply_markup=reply_markup)

    await query.answer()

async def handle_team_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка действий с командами."""
    query = update.callback_query
    if not db.is_admin(query.from_user.id):
        await query.answer("У вас нет доступа к этой функции.")
        return ConversationHandler.END

    action, team_id = query.data.split('_')[0], int(query.data.split('_')[2])

    if action == "approve":
        db.update_team_status(team_id, "approved")
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text(f"✅ Команда одобрена!")

    elif action == "reject":
        db.update_team_status(team_id, "rejected")
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text(f"❌ Команда отклонена!")

    elif action == "comment":
        context.user_data['commenting_team'] = team_id
        await query.message.reply_text(
            "Введите комментарий для команды:",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("Отмена", callback_data="cancel_comment")
            ]])
        )
        return WAITING_FOR_COMMENT

    await query.answer()


async def cancel_comment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отмена ввода комментария."""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Ввод комментария отменен.")
    context.user_data.pop('commenting_team', None)
    # Возвращаемся к меню команд, чтобы админ мог выбрать другую команду или действие
    await admin_teams_menu(update, context)
    return ConversationHandler.END

async def process_comment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка введенного комментария."""
    team_id = context.user_data.get('commenting_team')
    if not team_id:
        await update.message.reply_text("Произошла ошибка. Не удалось определить команду для комментария.")
        return ConversationHandler.END

    comment = update.message.text
    db.update_team_comment(team_id, comment)
    await update.message.reply_text(f"Комментарий для команды с ID {team_id} добавлен: {comment}")
    context.user_data.pop('commenting_team', None)
    # После добавления комментария возвращаемся к меню команд
    await admin_teams_menu(update, context)
    return ConversationHandler.END


async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Возвращение в админ-панель."""
    query = update.callback_query
    if not db.is_admin(query.from_user.id):
        await query.answer("У вас нет доступа к этой функции.")
        return

    keyboard = [
        [InlineKeyboardButton("📋 Список команд", callback_data="admin_teams_menu")],
        [InlineKeyboardButton("➕ Добавить админа", callback_data="admin_add_admin")],
        [InlineKeyboardButton("📊 Статистика", callback_data="admin_stats")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        "🔐 Админ-панель\n\nВыберите действие:",
        reply_markup=reply_markup
    )
    await query.answer()

async def admin_teams_list_pending(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показать список ожидающих команд."""
    await admin_teams_list(update, context, "pending")

async def admin_teams_list_approved(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показать список подтвержденных команд."""
    await admin_teams_list(update, context, "approved")

async def admin_teams_list_rejected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показать список отклоненных команд."""
    await admin_teams_list(update, context, "rejected")

# Новые функции для добавления админа
async def admin_add_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка нажатия кнопки 'Добавить админа'."""
    query = update.callback_query
    if not db.is_admin(query.from_user.id):
        await query.answer("У вас нет доступа к этой функции.")
        return ConversationHandler.END

    await query.answer()
    await query.edit_message_text(
        "Введите Telegram ID пользователя, которого вы хотите назначить администратором:\n\n"
        "Например: 123456789\n\n"
        "⚠️ Пользователь должен запустить бота хотя бы один раз, чтобы его можно было добавить как админа.",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("⬅️ Отмена", callback_data="admin_panel")
        ]])
    )
    
    # Устанавливаем состояние ожидания ввода ID
    return WAITING_FOR_ADMIN_ID

async def process_new_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка ввода ID нового админа."""
    admin_id = update.message.text.strip()
    
    # Проверка, что введенный текст - это число
    if not admin_id.isdigit():
        await update.message.reply_text(
            "❌ Ошибка: ID должен быть числовым значением.\n\nПожалуйста, введите корректный Telegram ID, или нажмите /admin для возврата в меню админа."
        )
        return WAITING_FOR_ADMIN_ID
    
    admin_id = int(admin_id)
    
    # Проверяем, есть ли пользователь в базе данных
    if not db.user_exists(admin_id):
        await update.message.reply_text(
            "❌ Ошибка: Пользователь с таким ID не найден в базе данных.\n\n"
            "Убедитесь, что пользователь взаимодействовал с ботом хотя бы один раз.\n\n"
            "Для возврата в меню админа, нажмите /admin."
        )
        return WAITING_FOR_ADMIN_ID
    
    # Проверяем, не является ли пользователь уже админом
    if db.is_admin(admin_id):
        await update.message.reply_text(
            "⚠️ Пользователь с ID %s уже является администратором." % admin_id,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("⬅️ Вернуться в панель админа", callback_data="admin_panel")
            ]])
        )
        return ConversationHandler.END
    
    # Добавляем пользователя как админа
    db.add_admin(admin_id)
    
    await update.message.reply_text(
        "✅ Пользователь с ID %s успешно добавлен как администратор!" % admin_id,
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("⬅️ Вернуться в панель админа", callback_data="admin_panel")
        ]])
    )
    
    return ConversationHandler.END

# Функция для показа статистики
async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показать статистику по командам и участникам."""
    query = update.callback_query
    if not db.is_admin(query.from_user.id):
        await query.answer("У вас нет доступа к этой функции.")
        return
    
    await query.answer()
    
    # Получаем статистику по командам
    pending_count = db.get_teams_count_by_status("pending")
    approved_count = db.get_teams_count_by_status("approved")
    rejected_count = db.get_teams_count_by_status("rejected")
    total_teams = pending_count + approved_count + rejected_count
    
    # Получаем общее количество игроков
    total_players = db.get_total_players_count()
    
    # Получаем количество уникальных капитанов
    unique_captains = db.get_unique_captains_count()
    
    # Формируем сообщение со статистикой
    stats_message = (
        "📊 **Статистика турнира**\n\n"
        f"👥 **Команды:**\n"
        f"• Всего команд: {total_teams}\n"
        f"• Ожидающие проверки: {pending_count}\n"
        f"• Подтвержденные: {approved_count}\n"
        f"• Отклоненные: {rejected_count}\n\n"
        f"🎮 **Игроки:**\n"
        f"• Всего игроков: {total_players}\n"
        f"• Уникальных капитанов: {unique_captains}\n"
    )
    
    # Кнопка возврата в админ-панель
    keyboard = [[InlineKeyboardButton("⬅️ Назад", callback_data="admin_panel")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        stats_message,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
