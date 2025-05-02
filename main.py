import logging
import yaml
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler,
)

# Состояния
WAITING_FOR_TASK_NAME, WAITING_FOR_VALUE_CATEGORY, WAITING_FOR_EFFORT, WAITING_FOR_EXPECTED_VALUE = range(4)

# Чтение конфигурации
with open("config.yaml") as f:
    config = yaml.safe_load(f)

# Google Sheets setup
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("google_credentials.json", scope)
client = gspread.authorize(creds)
sheet = client.open_by_key(config["spreadsheet_id"]).sheet1

# Логгирование
logging.basicConfig(level=logging.INFO)

# Словарь для хранения данных между шагами
user_data = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет! Напиши /add чтобы добавить задачу.")
    
async def add_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Как называется задача?")
    return WAITING_FOR_TASK_NAME

async def get_task_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_data[update.effective_user.id] = {"task": update.message.text}
    await update.message.reply_text("К какой ценности относится задача? (например: здоровье, работа)")
    return WAITING_FOR_VALUE_CATEGORY

async def get_value_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_data[update.effective_user.id]["category"] = update.message.text
    await update.message.reply_text("Укажи трудоёмкость в часах:")
    return WAITING_FOR_EFFORT

async def get_effort(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_data[update.effective_user.id]["effort"] = update.message.text
    await update.message.reply_text("Укажи ожидаемую эффективность (в рублях):")
    return WAITING_FOR_EXPECTED_VALUE

async def get_expected_value(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_data[update.effective_user.id]["value"] = update.message.text
    data = user_data[update.effective_user.id]

    # Сохраняем в Google Sheet
    sheet.append_row([
        data["task"],
        data["category"],
        data["effort"],
        data["value"]
    ])

    await update.message.reply_text("✅ Задача сохранена в таблицу!")
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Окей, отменено.")
    return ConversationHandler.END

def main():
    app = ApplicationBuilder().token(config["telegram_token"]).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("add", add_task)],
        states={
            WAITING_FOR_TASK_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_task_name)],
            WAITING_FOR_VALUE_CATEGORY: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_value_category)],
            WAITING_FOR_EFFORT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_effort)],
            WAITING_FOR_EXPECTED_VALUE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_expected_value)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv_handler)

    app.run_polling()

if __name__ == "__main__":
    main()
