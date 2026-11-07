import os
from dotenv import load_dotenv
load_dotenv()
os.environ["PYDANTIC_AI_NO_BANNER"] = "1"
import asyncio

import ipaddress
import socket
from datetime import datetime
from urllib.parse import urlparse

import httpx
import trafilatura
from ddgs import DDGS
from pydantic_ai import Agent
from pydantic_ai.messages import ModelRequest, UserPromptPart
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
# Comma-separated list of Telegram user IDs allowed to use the bot, e.g. "123456789,987654321"
ALLOWED_USER_IDS = [int(x) for x in os.environ["TELEGRAM_ALLOWED_USER_ID"].split(",") if x.strip()]

MAX_NOTE_LENGTH = 100
MAX_NOTES_FILE_SIZE = 100_000  # bytes (about 100 KB)
MAX_MESSAGE_LENGTH = 1000
MAX_SEARCH_RESULTS = 5
MAX_PAGE_CHARS = 4000  # keep tool output small so it fits the model's context
MAX_HISTORY_TURNS = 5  # how many of your past questions (plus their answers/tool calls) to remember

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

def web_search(query: str) -> str:
    """Search the internet for current information. Use this for news, current events,
    who currently holds a position (president, CEO, etc.), prices, recent releases,
    or anything that may have changed after your training. Returns titles, URLs and snippets."""
    try:
        results = DDGS().text(query, max_results=MAX_SEARCH_RESULTS)
    except Exception as error:
        return f"Search failed: {error}"
    if not results:
        return "No results found."
    return "\n\n".join(
        f"[{i}] {r.get('title', '')}\nURL: {r.get('href', '')}\n{r.get('body', '')}"
        for i, r in enumerate(results, 1)
    )

def _is_public_url(url: str) -> bool:
    """Block the agent from fetching localhost/LAN addresses (SSRF protection)."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return False
    try:
        addresses = socket.getaddrinfo(parsed.hostname, None)
    except socket.gaierror:
        return False
    return all(ipaddress.ip_address(a[4][0]).is_global for a in addresses)

def fetch_page(url: str) -> str:
    """Read the main text of a web page. Use this after web_search when the
    snippets are not enough to answer the question."""
    try:
        with httpx.Client(timeout=10, headers={"User-Agent": "Mozilla/5.0 (local-agent)"}) as client:
            for _ in range(5):  # follow redirects manually so each hop is checked
                if not _is_public_url(url):
                    return "Error: that URL is not allowed."
                response = client.get(url)
                if response.is_redirect:
                    url = str(response.url.join(response.headers["location"]))
                    continue
                break
            else:
                return "Error: too many redirects."
        response.raise_for_status()
    except Exception as error:
        return f"Could not fetch page: {error}"
    text = trafilatura.extract(response.text) or ""
    if not text:
        return "Could not extract readable text from that page."
    return text[:MAX_PAGE_CHARS]

agent = Agent(
    model,
    tools=[get_current_time, calculate, save_note, read_notes, clear_notes, web_search, fetch_page],
    instructions=(
        "You are a helpful personal assistant running 100% locally. "
        "Use your tools whenever they can help answer the question. "
        "Your built-in knowledge is out of date. For current events, who currently holds a role, "
        "prices, or anything that could have changed, call web_search first and answer from "
        "the results, not from memory. "
        "Always respond to the user's most recent message. "
        "Keep your answers short and friendly."
    ),
)

@agent.instructions
def todays_date() -> str:
    """Added fresh on every run so the model knows how stale its training data is."""
    return f"Today's date is {datetime.now():%A, %B %d, %Y}."

""" Telegram """
histories = {}  # one conversation history per chat (RAM only, cleared on restart)

def trim_history(messages, max_turns=MAX_HISTORY_TURNS):
    """Keep the last N questions and everything that followed each one.
    Always cuts at the start of a user question, so a tool call and its
    result never get split apart."""
    starts = [i for i, m in enumerate(messages)
              if isinstance(m, ModelRequest)
              and any(isinstance(p, UserPromptPart) for p in m.parts)]
    if len(starts) > max_turns:
        return messages[starts[-max_turns]:]
    return messages

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
        history = histories.get(chat_id, [])
        result = await agent.run(update.message.text, message_history=history)
        histories[chat_id] = trim_history(result.all_messages())
        reply = result.output
    except Exception as error:
        reply = f"Something went wrong: {error}"
    finally:
        stop_typing.set()   # tell the loop to stop
        await typing_task   # wait for any in-flight typing request to finish

    await update.message.reply_text(reply[:4096])  # Telegram's message size limit

def main():
    allowed_users = filters.User(user_id=ALLOWED_USER_IDS)

    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start, filters=allowed_users))
    app.add_handler(CommandHandler("reset", reset, filters=allowed_users))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & allowed_users, handle_message))

    print("Telegram agent running. Press Ctrl+C to stop.")
    app.run_polling()

if __name__ == "__main__":
    main()
