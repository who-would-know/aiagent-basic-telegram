## AI Agent Python Fun Examples
# init agent template from Tech with Tim Youtube

- Using Ollama model
- Basic agent tools for Ollama
- Added Telegram integration 

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
   # Setup Telegram Bot and vars, run this 
   uv run telegramagent.py
```
   uv will install the correct Python version and all dependencies automatically on first run.
