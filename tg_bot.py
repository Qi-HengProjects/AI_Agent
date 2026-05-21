import os
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from groq import Groq

# 1. 填入你的两把钥匙 (确保不要把引号删掉)
TELEGRAM_BOT_TOKEN = '8943658198:AAEaBgmsEetTUDEjizhxNG8dTI7ZQaT9u7g'
GROQ_API_KEY = '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'

# 初始化 Groq 客户端 (连接免费的云端大脑)
client = Groq(api_key=GROQ_API_KEY)


# 2. 定义大模型处理函数
def ask_groq(user_message):
    try:
        # 使用 Llama 3 8B 模型 (速度极快)
        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": "你是一个幽默、专业的 AI 助手。请用简明扼要的中文回答用户的问题。"
                },
                {
                    "role": "user",
                    "content": user_message
                }
            ],
            model="llama-3.3-70b-versatile",
        )
        return chat_completion.choices[0].message.content
    except Exception as e:
        return f"大脑连接出错啦: {e}"


# 3. 定义 Telegram 处理指令
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # 当用户发送 /start 时回复
    await update.message.reply_text('你好！我是你的云端 AI 助手，随便问我点什么吧！')


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # 接收用户的文字
    user_text = update.message.text
    print(f"收到消息: {user_text}")

    # 给用户发一个 "正在输入..." 的状态
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='typing')

    # 把文字丢给 Groq 大脑
    ai_response = ask_groq(user_text)

    # 将 AI 的回答发送回 Telegram
    await update.message.reply_text(ai_response)


# 4. 主函数：启动机器人
if __name__ == '__main__':
    print("机器人正在启动... 请到 Telegram 给它发消息！")

    # 建立 Application 实例
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # 绑定事件
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # 开始持续监听 Telegram
    app.run_polling()