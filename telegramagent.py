import os
os.environ["PYDANTIC_AI_NO_BANNER"] = "1"
import asyncio
from dotenv import load_dotenv
load_dotenv()

from datetime import datetime

from pydantic_ai import Agent
from pydantic_ai.models.ollama import OllamaModel
from pydantic_ai.providers.ollama import OllamaProvider
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

TELEGRAM_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
ALLOWED_USER_ID = int(os.environ["TELEGRAM_ALLOWED_USER_ID"])

MAX_NOTE_LENGTH = 100
MAX_NOTES_FILE_SIZE = 100_000  # bytes (about 100 KB) 
MAX_MESSAGE_LENGTH = 1000

model = OllamaModel(
    "qwen3.5:4b",
    provider=OllamaProvider(base_url="http://localhost:11434/v1")
)

""" Tools """
NOTES_FILE = "notes.txt"

def get_current_time() -> str:
    """Get the current date and time."""
    return datetime.now().strftime("%A, %B %d, %Y at %I:%M %p")

def calculate(expression: str) -> str:
    """Evaluate a basic math expression, e.g. '23 * 7 + 1'."""
    if not set(expression) <= set("0123456789+-*/(). "):
        return "Error: only numbers and + - * / ( ) are allowed."
    try:
        return str(eval(expression))
    except Exception as error:
        return f"Error: {error}"

def save_note(note: str) -> str:
    """Save a short note so it can be recalled later. If it is to long don't save it or if the note file is full don't save it."""
    if len(note) > MAX_NOTE_LENGTH:
        return f"Way too much!  Notes must be {MAX_NOTE_LENGTH} characters or less."
    if os.path.exists(NOTES_FILE) and os.path.getsize(NOTES_FILE) > MAX_NOTES_FILE_SIZE:
        return "Way too much! The notes file is full."
    with open(NOTES_FILE, "a", encoding="utf-8") as file:
        file.write(f"- {note}\n")
    return f"Saved note: {note}"

def read_notes() -> str:
    """Read back all previously saved notes."""
    if not os.path.exists(NOTES_FILE):
        return "No notes saved yet."
    with open(NOTES_FILE, encoding="utf-8") as file:
        return file.read()

def clear_notes() -> str:
   """Clears the notes file."""
   if not os.path.exists(NOTES_FILE):
      return "No notes added yet"
   with open(NOTES_FILE, "r+", encoding="utf-8") as file:
      file.seek(0)
      file.truncate(0)
   return "Note file has been cleared!"

agent = Agent(
    model,
    tools=[get_current_time, calculate, save_note, read_notes, clear_notes],
    instructions=(
        "You are a helpful personal assistant running 100% locally. "
        "Use your tools whenever they can help answer the question. "
        "Always respond to the user's most recent message. "
        "Keep your answers short and friendly."
    ),
)

""" Telegram """
histories = {}  # one conversation history per chat

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Hi! I'm your local agent. Send /reset to start fresh.")

async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    histories.pop(update.effective_chat.id, None)
    await update.message.reply_text("Conversation cleared.")

async def keep_typing(bot, chat_id, stop):
    """Resend 'typing...' every 4 seconds until stop is set."""
    while not stop.is_set():
        try:
            await bot.send_chat_action(chat_id, ChatAction.TYPING)
        except Exception:
            pass  # a failed typing update shouldn't break anything
        try:
            await asyncio.wait_for(stop.wait(), timeout=4)
        except TimeoutError:
            pass  # 4 seconds passed, loop and send typing again

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(update.message.text) > MAX_MESSAGE_LENGTH:
        await update.message.reply_text("Way too much! Keep messages under 1000 characters.")
        return

    chat_id = update.effective_chat.id
    stop_typing = asyncio.Event()
    typing_task = asyncio.create_task(keep_typing(context.bot, chat_id, stop_typing))

    try:
        history = histories.get(chat_id, [])[-10:]
        result = await agent.run(update.message.text, message_history=history)
        histories[chat_id] = result.all_messages()
        reply = result.output
    except Exception as error:
        reply = f"Something went wrong: {error}"
    finally:
        stop_typing.set()   # tell the loop to stop
        await typing_task   # wait for any in-flight typing request to finish

    await update.message.reply_text(reply[:4096])  # Telegram's message size limit

def main():
    only_me = filters.User(user_id=ALLOWED_USER_ID)

    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start, filters=only_me))
    app.add_handler(CommandHandler("reset", reset, filters=only_me))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & only_me, handle_message))

    print("Telegram agent running. Press Ctrl+C to stop.")
    app.run_polling()

if __name__ == "__main__":
    main()
