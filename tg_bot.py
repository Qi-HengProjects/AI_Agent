import os
import json
import logging
import sys
from datetime import datetime, timezone, timedelta
import yfinance as yf
import asyncio

import tree_sitter_c_sharp
from groq import AsyncGroq
from dotenv import load_dotenv
from huggingface_hub.cli.inference_endpoints import update
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, CallbackContext


# SECTION 1: SYSTEM INITIALIZATION & SECURITY CHECK (Fail-Fast)
load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv('BOT_TOKEN')
GROQ_API_KEY = os.getenv('API_KEY')

# Best Practice: Terminate immediately if critical environmental variables are missing
if not TELEGRAM_BOT_TOKEN or not GROQ_API_KEY:
    logging.critical("Did not detect any telegram bot token or api key") #highest level of system issue
    sys.exit(1)

groq_client = AsyncGroq(api_key=GROQ_API_KEY)
MODEL_NAME = "openai/gpt-oss-120b"

# Configure structured logging format for debugging production metrics
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)


# SECTION 2: LOCAL TOOLS DEFINITION (Agent's Execution Layer)
def get_current_time(tz_offset_hours: int = 8) -> str: #return type is string
    #get accurate current date and time
    tz = timezone(timedelta(hours=tz_offset_hours))
    current_time = datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S")
    return json.dumps({"current_time": current_time, "timezone_offset": f"UTC+{tz_offset_hours}"})

def get_stocks_price(ticker: str) -> str:
    try:
        # Defensive programming: Strip whitespaces and force uppercase
        clean_ticker = ticker.strip().upper()
        stock = yf.Ticker(clean_ticker)
        price = stock.fast_info['last_price']
        currency = stock.fast_info.get('currency', 'USD')

        return json.dumps({
            # Graceful error catching: Feed the error payload to LLM as context rather than crashing
            "ticker": clean_ticker,
            "current_price": round(price, 2),
            "currency": currency,
            "status" : "success"
        })
    except Exception as e:
        return json.dumps({
            "ticker": ticker,
            "status": "error",
            "message": f"Unable to get stock price for {ticker}, reason: {str(e)}"
        })

AVAILABLE_FUNCTIONS = {
    "get_current_time": get_current_time,
    "get_stocks_price": get_stocks_price,
}


# SECTION 3: TOOL SCHEMAS DEFINITION (The LLM Manifest Docs)
TIME_TOOL_SCHEMA = {
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

# tools 2
STOCK_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "get_stocks_price",
        "description": "Get the latest price of selected stock. When users ask for stock price, trend, info of a company, use this tool.",
        "parameters": {
            "type": "object",
            "properties": {
                "ticker": {
                    "type": "string",
                    "description": "Short form name of a stock, for example, the name of Apple stock is AAPL."
                }
            },
            "required": ["ticker"] # 'ticker' parameter is mandatory for execution
        }
    }
}

# The array schema wrapper required by Groq/OpenAI architecture gateway
TOOLS_SCHEMA = [
    TIME_TOOL_SCHEMA,
    STOCK_TOOL_SCHEMA,
]


# SECTION 4: CORE AGENT ORCHESTRATION PIPELINE (Intercept & Route)
async def handle_message(update: Update, context: ContextTypes):
    user_text = update.message.text
    chat_id = update.message.chat_id

    await context.bot.send_chat_action(chat_id=chat_id,action= "typing")

    messages = [
        {"role": "system", "content": "You are now a helpful AI assistant. You have the ability to use tools to fetch the latest information."},
        {"role": "user", "content": user_text}
    ]

    try:
        # PHASE 1: Send query and tool specs to LLM for initial execution strategy
        response = await groq_client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            tools=TOOLS_SCHEMA,
            tool_choice="auto"
        )

        response_message = response.choices[0].message

        # GATEKEEPER: Check if LLM requested a local function invocation signal
        if response_message.tool_calls:
            logging.info("Agent decision: Tools available")

            # API Constraint: Must append the original assistant tool request block back to history array
            messages.append({
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments
                        }
                    } for tc in response_message.tool_calls
                ]
            })

            # PHASE 2: Local tool execution loop
            for tool_call in response_message.tool_calls:
                function_name = tool_call.function.name
                function_args = json.loads(tool_call.function.arguments) if tool_call.function.arguments else {}

                function_to_call = AVAILABLE_FUNCTIONS.get(function_name)
                if function_to_call:
                    logging.info(f"Calling {function_name}")
                    function_response = function_to_call(**function_args)

                    messages.append({
                        "tool_call_id": tool_call.id,
                        "role": "tool",
                        "name": function_name,
                        "content": function_response,
                    })

            # PHASE 3: Re-submit enriched context back to LLM for final synthesis translation
            final_response = await groq_client.chat.completions.create(
                model=MODEL_NAME,
                messages=messages
            )

            await update.message.reply_text(final_response.choices[0].message.content)

        else:
            # PHASE 4: NORMAL CHAT PIPELINE (Handling Vibe & Chunks)
            logging.info("Normal chat")
            chat_reply = response_message.content

            if chat_reply:
                # Telegram Hard Bottleneck: 4096 character threshold. 3500 provides safe margin.
                MAX_CHUNK_SIZE = 3500

                # Sliding Window Chunking Strategy to bypass API bottleneck
                if len(chat_reply) > MAX_CHUNK_SIZE:
                    logging.info(f"Text segmentation: {len(chat_reply)}")

                    for i in range(0, len(chat_reply), MAX_CHUNK_SIZE):
                        chunk = chat_reply[i: i + MAX_CHUNK_SIZE]
                        await update.message.reply_text(chunk)
                        await asyncio.sleep(0.2) # Throttle to prevent Telegram API rate-limit penalty

                else:
                    await update.message.reply_text(chat_reply)
            else:
                await update.message.reply_text("Sorry, I don't know how to answer that.")

    except Exception as e:
        logging.error(f"Error: {e}")
        await update.message.reply_text(f"Sorry there is an error while processing this request: {e}")


# SECTION 5: TELEGRAM APPLICATION DAEMON RUNNER
def main():
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("Bot started")
    app.run_polling()

if __name__ == "__main__":
    main()


