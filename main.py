python
import yaml
from telegram import Update
from telegram.ext import Updater, CommandHandler, CallbackContext
from google.oauth2 import service_account
from googleapiclient.discovery import build

# Чтение конфига
with open('config.yaml', 'r') as file:
    config = yaml.safe_load(file)
TELEGRAM_TOKEN = config['telegram']['token']

# Настройка Google Sheets
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
SPREADSHEET_ID = '1yF44tEwMDRDEE_8ZYLbAJcL5vHtMaCWnP2yUSKxoxCo'  # Замени на ID своей Google Таблицы
RANGE_NAME = 'Sheet1!A2:F'  # Диапазон для задач (со 2-й строки)

def get_sheets_service():
    creds = service_account.Credentials.from_service_account_file(
        'google_credentials.json', scopes=SCOPES)
    service = build('sheets', 'v4', credentials=creds)
    return service.spreadsheets()

# Команда /add
def add_task(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    args = context.args
    if len(args) < 2:
        update.message.reply_text('Используй: /add <задача> <дата_время> [приоритет]\nПример: /add Купить молоко 2023-10-15_14:00 High')
        return
    
    task = ' '.join(args[:-1]) if len(args) > 2 else args[0]
    due_date = args[-1] if len(args) > 2 else args[1]
    priority = args[-1] if len(args) % 2 == 1 and args[-1] in ['Low', 'Medium', 'High'] else 'Medium'
    
    sheets = get_sheets_service()
    # Получаем текущие задачи для определения ID
    result = sheets.values().get(spreadsheetId=SPREADSHEET_ID, range=RANGE_NAME).execute()
    values = result.get('values', [])
    new_id = len(values) + 1
    
    # Новая задача
    new_task = [new_id, user_id, task, due_date, priority, 'Pending']
    
    # Добавляем в таблицу
    sheets.values().append(
        spreadsheetId=SPREADSHEET_ID,
        range=RANGE_NAME,
        valueInputOption='RAW',
        body={'values': [new_task]}
    ).execute()
    
    update.message.reply_text(f'Задача "{task}" добавлена на {due_date}!')

# Команда /list
def list_tasks(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    sheets = get_sheets_service()
    result = sheets.values().get(spreadsheetId=SPREADSHEET_ID, range=RANGE_NAME).execute()
    tasks = result.get('values', [])
    
    user_tasks = [f'ID: {task[0]}, Задача: {task[2]}, Срок: {task[3]}, Приоритет: {task[4]}, Статус: {task[5]}'
                  for task in tasks if task[1] == str(user_id)]
    
    response = '\n'.join(user_tasks) if user_tasks else 'Нет задач!'
    update.message.reply_text(response)

# Основная функция
def main():
    updater = Updater(TELEGRAM_TOKEN)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("add", add_task))
    dp.add_handler(CommandHandler("list", list_tasks))
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
