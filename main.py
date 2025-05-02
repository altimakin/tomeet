import yaml
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from pytz import timezone
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, ConversationHandler, 
    ContextTypes, filters
)
import gspread

# Чтение конфигурационного файла
def load_config(file_path="config.yaml"):
    with open(file_path, "r") as file:
        return yaml.safe_load(file)

# Загрузка конфигурации
config = load_config()

# Настройки Google Sheets
CREDENTIALS_FILE = config["google"]["credentials_file"]
gc = gspread.service_account(filename=CREDENTIALS_FILE)

# Состояния диалога
REGISTER_TEAM, SELECT_OR_ADD_PROJECT, ADD_NEW_PROJECT, ADD_BACKUP, ASK_CLIENT_TEAM, CHOOSE_NEXT_ACTION = range(6)

# Инициализация планировщика
scheduler = BackgroundScheduler()
scheduler.start()

# Список чатов для рассылки
registered_chats = set()

# Функция для получения или создания листа команды
def get_or_create_team_sheet(team_name):
    try:
        sheet = gc.open(config["google"]["spreadsheet_name"])
        worksheet = sheet.worksheet(team_name)
    except gspread.exceptions.WorksheetNotFound:
        worksheet = sheet.add_worksheet(title=team_name, rows=100, cols=5)
        worksheet.append_row(["Проект", "Команда клиента", "Ссылка на бэкап", "Дата добавления"])
    return worksheet

# Регистрация чата
async def register_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id not in registered_chats:
        registered_chats.add(chat_id)
        await update.message.reply_text("Этот чат успешно зарегистрирован для автоматических запросов!")
    else:
        await update.message.reply_text("Этот чат уже зарегистрирован.")
    return ConversationHandler.END

# Регистрация команды
async def register_team(update: Update, context: ContextTypes.DEFAULT_TYPE):
    existing_teams = [[sheet.title] for sheet in gc.open(config["google"]["spreadsheet_name"]).worksheets()]
    await update.message.reply_text(
        "Добро пожаловать! Введите название команды или выберите из списка существующих:",
        reply_markup=ReplyKeyboardMarkup([["Создать новую команду"]] + existing_teams, one_time_keyboard=True)
    )
    return REGISTER_TEAM

async def save_team(update: Update, context: ContextTypes.DEFAULT_TYPE):
    team_name = update.message.text
    if team_name == "Создать новую команду":
        await update.message.reply_text("Введите название для новой команды:")
        return REGISTER_TEAM
    else:
        context.user_data['team_name'] = team_name
        await update.message.reply_text(f"Вы выбрали команду '{team_name}'.")
        return await select_or_add_project(update, context)

# Выбор или добавление проекта
async def select_or_add_project(update: Update, context: ContextTypes.DEFAULT_TYPE):
    team_name = context.user_data['team_name']
    worksheet = get_or_create_team_sheet(team_name)
    projects = list(set(row[0] for row in worksheet.get_all_values()[1:] if row[0]))
    
    if projects:
        await update.message.reply_text(
            "Выберите проект или добавьте новый:",
            reply_markup=ReplyKeyboardMarkup([["Добавить новый проект"]] + [[p] for p in projects], one_time_keyboard=True)
        )
    else:
        await update.message.reply_text("В этой команде ещё нет проектов. Добавьте новый проект:")
        return ADD_NEW_PROJECT

    return SELECT_OR_ADD_PROJECT

# Добавление нового проекта
async def add_new_project(update: Update, context: ContextTypes.DEFAULT_TYPE):
    project_name = update.message.text
    team_name = context.user_data['team_name']
    worksheet = get_or_create_team_sheet(team_name)

    if project_name == "Добавить новый проект":
        await update.message.reply_text("Введите название нового проекта:")
        return ADD_NEW_PROJECT

    worksheet.append_row([project_name, "", "", ""])
    context.user_data['project_name'] = project_name
    await update.message.reply_text(f"Проект '{project_name}' успешно добавлен.")
    return await ask_for_client_team(update, context)

# Выбор существующего проекта
async def select_existing_project(update: Update, context: ContextTypes.DEFAULT_TYPE):
    project_name = update.message.text
    context.user_data['project_name'] = project_name
    await update.message.reply_text(f"Вы выбрали проект '{project_name}'.")
    return await ask_for_client_team(update, context)

# Запрос названия команды клиента
async def ask_for_client_team(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Введите название команды клиента для этого проекта:")
    return ASK_CLIENT_TEAM

async def save_client_team(update: Update, context: ContextTypes.DEFAULT_TYPE):
    client_team_name = update.message.text
    context.user_data['client_team_name'] = client_team_name
    await update.message.reply_text(f"Команда клиента '{client_team_name}' сохранена.")
    return await ask_for_backup(update, context)

# Запрос ссылки на бэкап
async def ask_for_backup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Введите ссылку на бэкап для этого проекта:")
    return ADD_BACKUP

# Добавление бэкапа
async def add_backup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    backup_link = update.message.text
    team_name = context.user_data['team_name']
    project_name = context.user_data['project_name']
    client_team_name = context.user_data['client_team_name']
    worksheet = get_or_create_team_sheet(team_name)
    
    worksheet.append_row([project_name, client_team_name, backup_link, datetime.now().strftime("%Y-%m-%d %H:%M:%S")])
    await update.message.reply_text(
        f"Ссылка '{backup_link}' добавлена в проект '{project_name}' для команды клиента '{client_team_name}'."
    )
    return await choose_next_action(update, context)

# Выбор следующего действия
async def choose_next_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Что вы хотите сделать дальше?",
        reply_markup=ReplyKeyboardMarkup(
            [
                ["Добавить ещё одну ссылку"],
                ["Выбрать другой проект"],
                ["Выбрать другую команду клиента"],
                ["Завершить"]
            ],
            one_time_keyboard=True
        )
    )
    return CHOOSE_NEXT_ACTION

# Обработка выбора следующего действия
async def handle_next_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    action = update.message.text
    if action == "Добавить ещё одну ссылку":
        return await ask_for_backup(update, context)
    elif action == "Выбрать другой проект":
        return await select_or_add_project(update, context)
    elif action == "Выбрать другую команду клиента":
        return await ask_for_client_team(update, context)
    elif action == "Завершить":
        await update.message.reply_text("Работа завершена. Спасибо!")
        return ConversationHandler.END
    else:
        await update.message.reply_text("Пожалуйста, выберите одно из предложенных действий.")
        return CHOOSE_NEXT_ACTION

# Запрос данных каждый день в 11:00 по Москве
def scheduled_backup_request():
    moscow_time = timezone("Europe/Moscow")
    current_time = datetime.now(moscow_time).strftime("%Y-%m-%d %H:%M:%S")
    for chat_id in registered_chats:
        application.bot.send_message(
            chat_id,
            f"Ежедневный запрос данных о бэкапах. Сейчас {current_time}. Пожалуйста, обновите данные."
        )

# Главная функция
def main():
    global application
    TELEGRAM_TOKEN = config["telegram"]["token"]

    application = Application.builder().token(TELEGRAM_TOKEN).build()

    # Запуск задачи в 11:00 по Москве
    scheduler.add_job(
        scheduled_backup_request,
        "cron",
        hour=11,
        minute=0,
        timezone="Europe/Moscow"
    )

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", register_team)],
        states={
            REGISTER_TEAM: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_team)],
            SELECT_OR_ADD_PROJECT: [
                MessageHandler(filters.Regex("Добавить новый проект"), add_new_project),
                MessageHandler(filters.TEXT & ~filters.COMMAND, select_existing_project),
            ],
            ADD_NEW_PROJECT: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_new_project)],
            ASK_CLIENT_TEAM: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_client_team)],
            ADD_BACKUP: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_backup)],
            CHOOSE_NEXT_ACTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_next_action)],
        },
        fallbacks=[CommandHandler("cancel", lambda u, c: u.message.reply_text("Операция отменена."))]
    )

    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("register_chat", register_chat))
    application.run_polling()

if __name__ == "__main__":
    main()
