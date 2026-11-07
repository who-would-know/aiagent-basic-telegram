## AI Agent Python Fun Examples
### init agent template from Tech with Tim Youtube

- Using Ollama model
- Basic agent tools for Ollama
- Added Telegram integration
- Added web search so the model can answer with current info (news, who holds a role, prices, etc.)

## Running locally with uv

0. Install Ollama locally. I used model 'qwen3.5:4b' but you can change that for others.

1. Install uv:
   - macOS/Linux: `curl -LsSf https://astral.sh/uv/install.sh | sh`
   - Windows (PowerShell): `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`

2. Clone and enter the repo:
```
   git clone https://github.com/who-would-know/aiagent-basic-telegram.git
   cd aiagent-basic-telegram
```

3. Run it:
```
   # Basic example
   uv run agent.py

   # Telegram bot (create the .env file below first)
   uv run telegramagent.py

   # Telegram bot + web search, so answers aren't stuck at the model's training date
   uv run aisearchagent.py
```
   uv will install the correct Python version and all dependencies automatically on first run.

## Telegram setup (.env file)

The Telegram bots read their settings from a `.env` file in the same folder as the scripts. Create it with:

```
TELEGRAM_BOT_TOKEN=123456789:ABCdefGhIJKlmNoPQRstuVWXyz
TELEGRAM_ALLOWED_USER_ID=111111111,222222222
```

- `TELEGRAM_BOT_TOKEN`: message **@BotFather** on Telegram, send `/newbot`, and copy the token it gives you.
- `TELEGRAM_ALLOWED_USER_ID`: the Telegram user IDs allowed to talk to the bot. Message **@userinfobot** to get yours. For more than one person, separate the IDs with commas. Anyone not on the list is ignored.

Never commit this file. Make sure `.env` is in `.gitignore`:
```
echo ".env" >> .gitignore
```

## Web search agent (aisearchagent.py)

Local models only know what was in their training data, so a question like "who is the president?" can get an outdated answer. `aisearchagent.py` adds two tools the model can call on its own:

- `web_search`: searches DuckDuckGo (no API key needed) and returns the top results.
- `fetch_page`: reads the main text of a page when the search snippets aren't enough. It blocks localhost and LAN addresses so a web page can't trick the agent into poking at your network.

The current date is also passed to the model on every message, so it knows how stale its own knowledge is.

Tip: search results take up room in the prompt. If answers get cut off or the model forgets your instructions, raise Ollama's context length before starting it:
```
OLLAMA_CONTEXT_LENGTH=16384
```

Conversation history is kept in memory per chat (last 5 questions) and clears on restart or with `/reset`.

## Running it 24/7 with pm2

```
pm2 start aisearchagent.py --name telegram-agent --interpreter ./.venv/bin/python --interpreter-args="-u"
pm2 save
```

After code or `.env` changes: `pm2 restart telegram-agent`
