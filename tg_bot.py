import os
import json
import logging
import sys
from datetime import datetime, timezone, timedelta
from groq import AsyncGroq
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, CallbackContext

#setting up
load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv('BOT_TOKEN')
GROQ_API_KEY = os.getenv('API_KEY')
groq_client = AsyncGroq(api_key=GROQ_API_KEY)
MODEL_NAME = "openai/gpt-oss-120b"

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

if not TELEGRAM_BOT_TOKEN or not GROQ_API_KEY:
    logging.critical("Did not detect any telegram bot token or api key") #highest level of system issue
    sys.exit(1)



#setting up tools for the agent
def get_current_time(tz_offset_hours: int = 8) -> str: #return type is string
    #get accurate current date and time
    tz = timezone(timedelta(hours=tz_offset_hours))
    current_time = datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S")
    return json.dumps({"current_time": current_time, "timezone_offset": f"UTC+{tz_offset_hours}"})

AVAILABLE_FUNCTIONS = {
    "get_current_time": get_current_time,
}

# tools (follow the structure of Groq / OpenAI)
TOOLS_SCHEMA = {
    "type": "function",
    "function": {
        "name": "get_current_time",
        "description": "Get the current time and date. Default return UTC+8.",
        "parameters": {
            "type": "object",
            "properties": {
                "tz_offset_hours": {
                    "type":"integer",
                    "description": "The offset of different time zone."
                }
            },
            "required": []
        }
    }
}

#core agent stop and executing

async def handle_message(update: Update, context: ContextTypes):
    user_text = update.message.text
    chat_id = update.message.chat_id