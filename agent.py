import os
os.environ["PYDANTIC_AI_NO_BANNER"] = "1"

from datetime import datetime

from pydantic_ai import Agent
from pydantic_ai.models.ollama import OllamaModel
from pydantic_ai.providers.ollama import OllamaProvider

model = OllamaModel(
    "qwen3.5:4b",
    provider=OllamaProvider(base_url="http://localhost:11434/v1")
)

""" Tools """
NOTES_FILE = "notes.txt"

def get_current_time() -> str:
    """Get the current date and time. """
    return datetime.now().strftime("%A, %B, %d, %Y at %I:%M %p")

def calculate(expression: str) -> str:
    """Evaluate a basic math expressio, e.g. '23 * 7 +1'."""
    if not set(expression) <= set("0123456789+-*/(). "):
        return "Error: only numbers and + - * / ( ) are allowed."
    try:
        return str(eval(expression))
    except Exception as error:
        return f"Error: {error}"

def save_note(note: str) -> str:
    """Save a short note so it can be recalled later."""
    with open(NOTES_FILE, "a", encoding="utf-8") as file:
        file.write(f"- {note}\n")
    return "Note saved."

def read_notes() -> str:
    """Read back all previously saved notes."""
    if not os.path.exists(NOTES_FILE):
        return "No notes saved yet."
    with open(NOTES_FILE, encoding="utf-8") as file:
        return file.read()

agent = Agent(
    model,
    tools=[get_current_time, calculate, save_note, read_notes],
    instructions=(
        "You are a helpful personal assistant running 100% locally. "
        "Use your tools whenever they can help answer the question. "
        "Keep your answers short and friendly. "
    ),
)

def main():
    print("Local agent ready! Type 'quit' to exist.\n")
    history=[]
    while True:
        user_input = input ("You: ")
        if user_input.strip().lower() in ("quit", "exit"):
            break
        result = agent.run_sync(user_input, message_history=history)
        history = result.all_messages()
        print(f"\nAgent: {result.output}\n")

if __name__ == "__main__":
    main()