from telegram import Update, WebAppInfo
from telegram.ext import Application, CommandHandler, MessageHandler, filters

BOT_TOKEN = "8031510962:AAFx7relBmfwGKUs4eZuhZIbCIKqfl-Zq08"

# URL вашего Mini App (Ngrok или локальный)
WEB_APP_URL = "https://896a-109-200-157-21.ngrok-free.app"

async def start(update: Update, context):
    # Отправляем кнопку с Mini App
    await update.message.reply_text(
        "Нажмите кнопку, чтобы открыть Mini App:",
        reply_markup={
            "inline_keyboard": [[
                {
                    "text": "✨ Открыть Mini App",
                    "web_app": {"url": WEB_APP_URL}
                }
            ]]
        }
    )

async def handle_web_app_data(update: Update, context):
    # Получаем данные из Mini App
    data = update.message.web_app_data.data
    await update.message.reply_text(f"🤖 Бот получил данные: {data}")

# Запуск бота
app = Application.builder().token(BOT_TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, handle_web_app_data))
app.run_polling()
