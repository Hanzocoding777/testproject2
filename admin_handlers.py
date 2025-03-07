from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler, ConversationHandler, MessageHandler, filters
from database import Database

db = Database()

WAITING_FOR_COMMENT = 1

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Показать админ-панель."""
    if not db.is_admin(update.effective_user.id):
        await update.message.reply_text("У вас нет доступа к админ-панели.")
        return ConversationHandler.END

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
        [InlineKeyboardButton(f"Ожидающие команды ({pending_count})", callback_data="show_teams_pending")],
        [InlineKeyboardButton(f"Подтвержденные команды ({approved_count})", callback_data="show_teams_approved")],
        [InlineKeyboardButton(f"Отклоненные команды ({rejected_count})", callback_data="show_teams_rejected")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="back_to_admin")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        "Выберите категорию команд для просмотра:",
        reply_markup=reply_markup
    )
    await query.answer()
    return ConversationHandler.WAITING

async def show_teams_by_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показать список команд определенного статуса."""
    query = update.callback_query
    if not db.is_admin(query.from_user.id):
        await query.answer("У вас нет доступа к этой функции.")
        return

    status = query.data.split("_")[-1]  # show_teams_pending -> pending
    teams = db.get_all_teams_by_status(status)

    if not teams:
        # Возвращаемся к меню выбора статуса
        return await admin_teams_menu(update, context)

    # Создаем кнопки для каждой команды
    keyboard = []
    for team in teams:
        keyboard.append([InlineKeyboardButton(
            f"{team['team_name']}", 
            callback_data=f"view_team_{team['id']}"
        )])
    keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data="admin_teams_menu")])

    await query.edit_message_text(
        f"Выберите команду для просмотра:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    await query.answer()

async def view_team(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показать информацию о конкретной команде."""
    query = update.callback_query
    if not db.is_admin(query.from_user.id):
        await query.answer("У вас нет доступа к этой функции.")
        return

    team_id = int(query.data.split("_")[-1])
    team = next((t for t in db.get_all_teams() if t['id'] == team_id), None)

    if not team:
        await query.answer("Команда не найдена.")
        return await admin_teams_menu(update, context)

    players_list = "\n".join([f"• {p[0]} – {p[1]}" for p in team['players']])
    message = (
        f"🎮 Команда: {team['team_name']}\n"
        f"📅 Дата регистрации: {team['registration_date']}\n"
        f"📱 Контакт капитана: {team['captain_contact']}\n"
        f"📊 Статус: {team['status']}\n"
        f"💭 Комментарий: {team['admin_comment'] or 'Нет'}\n\n"
        f"👥 Игроки:\n{players_list}"
    )

    keyboard = [
        [
            InlineKeyboardButton("✅ Одобрить", callback_data=f"approve_team_{team_id}"),
            InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_team_{team_id}")
        ],
        [InlineKeyboardButton("💬 Комментарий", callback_data=f"comment_team_{team_id}")],
        [InlineKeyboardButton("⬅️ Назад", callback_data=f"show_teams_{team['status']}")]
    ]

    await query.edit_message_text(
        message,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    await query.answer()

async def handle_team_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка действий с командами."""
    query = update.callback_query
    if not db.is_admin(query.from_user.id):
        await query.answer("У вас нет доступа к этой функции.")
        return ConversationHandler.END

    action, team_id = query.data.split('_')[0], int(query.data.split('_')[-1])
    
    # Получаем текущий статус команды перед изменением
    team = next((t for t in db.get_all_teams() if t['id'] == team_id), None)
    if not team:
        await query.answer("Команда не найдена.")
        return await admin_teams_menu(update, context)
    
    current_status = team['status']

    if action == "approve":
        db.update_team_status(team_id, "approved")
        await query.answer("✅ Команда одобрена!")
    elif action == "reject":
        db.update_team_status(team_id, "rejected")
        await query.answer("❌ Команда отклонена!")

    if action in ["approve", "reject"]:
        # Проверяем, остались ли еще команды с текущим статусом
        teams_left = db.get_all_teams_by_status(current_status)
        if teams_left:
            # Если есть еще команды, показываем их список
            return await show_teams_by_status(update, context)
        else:
            # Если команд не осталось, возвращаемся к меню выбора статуса
            return await admin_teams_menu(update, context)
    
    elif action == "comment":
        context.user_data['commenting_team'] = team_id
        keyboard = [[InlineKeyboardButton("Отмена", callback_data=f"view_team_{team_id}")]]
        await query.edit_message_text(
            "Введите комментарий для команды:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return WAITING_FOR_COMMENT

# Добавляем новую функцию для сохранения комментария
async def save_comment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Сохранить комментарий администратора к команде."""
    if not db.is_admin(update.effective_user.id):
        await update.message.reply_text("У вас нет доступа к этой функции.")
        return ConversationHandler.END
    
    team_id = context.user_data.get('commenting_team')
    if not team_id:
        await update.message.reply_text("Произошла ошибка: не найден ID команды. Попробуйте еще раз.")
        return ConversationHandler.END
    
    comment_text = update.message.text
    
    # Сохраняем комментарий в базе данных
    try:
        success = db.update_team_comment(team_id, comment_text)
        if success:
            await update.message.reply_text("✅ Комментарий успешно сохранен.")
            
            # Обновляем информацию о команде и показываем ее снова
            team = next((t for t in db.get_all_teams() if t['id'] == team_id), None)
            if team:
                players_list = "\n".join([f"• {p[0]} – {p[1]}" for p in team['players']])
                message = (
                    f"🎮 Команда: {team['team_name']}\n"
                    f"📅 Дата регистрации: {team['registration_date']}\n"
                    f"📱 Контакт капитана: {team['captain_contact']}\n"
                    f"📊 Статус: {team['status']}\n"
                    f"💭 Комментарий: {comment_text}\n\n"
                    f"👥 Игроки:\n{players_list}"
                )

                keyboard = [
                    [
                        InlineKeyboardButton("✅ Одобрить", callback_data=f"approve_team_{team_id}"),
                        InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_team_{team_id}")
                    ],
                    [InlineKeyboardButton("💬 Комментарий", callback_data=f"comment_team_{team_id}")],
                    [InlineKeyboardButton("⬅️ Назад", callback_data=f"show_teams_{team['status']}")]
                ]
                
                await update.message.reply_text(
                    message,
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
        else:
            await update.message.reply_text("❌ Ошибка сохранения комментария. Попробуйте еще раз.")
    except Exception as e:
        await update.message.reply_text(f"❌ Произошла ошибка при сохранении комментария: {str(e)}")
    
    # Возвращаемся в режим ожидания
    return ConversationHandler.WAITING

async def back_to_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Возврат к главному меню админ-панели."""
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
