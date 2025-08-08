#!/usr/bin/env python3
import sys
import json
import os
import time
from openai import OpenAI

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "../config/config.json")

def load_config():
    with open(CONFIG_PATH, "r") as f:
        return json.load(f)

def get_api_key_and_assistant_id(config, assistant_name="ArchLinuxAssistant"):
    api_key = config["api_keys"]["default_key"]
    assistant_id = config["assistants"][assistant_name]["openai_assistant_id"]
    return api_key, assistant_id

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 ai.py [assistant_name] your question")
        sys.exit(1)

    config = load_config()
    assistants = config.get("assistants", {})

    # Preveri, ali je prvi argument ime asistenta
    if sys.argv[1] in assistants:
        assistant_name = sys.argv[1]
        user_input = " ".join(sys.argv[2:])
    else:
        assistant_name = "ArchLinuxAssistant"
        user_input = " ".join(sys.argv[1:])

    api_key, assistant_id = get_api_key_and_assistant_id(config, assistant_name)
    print(f"Using assistant: {assistant_name} (ID: {assistant_id})")

    client = OpenAI(api_key=api_key)
    print(f"User input: {user_input}")

    thread = client.beta.threads.create()

    client.beta.threads.messages.create(
        thread_id=thread.id,
        role="user",
        content=user_input,
    )

    run = client.beta.threads.runs.create(
        thread_id=thread.id,
        assistant_id=assistant_id,
    )

    while run.status not in {"completed", "failed", "cancelled", "expired"}:
        time.sleep(1)
        run = client.beta.threads.runs.retrieve(
            thread_id=thread.id,
            run_id=run.id,
        )

    if run.status == "completed":
        messages = client.beta.threads.messages.list(thread_id=thread.id)
        for message in messages.data:
            if message.role == "assistant" and message.content:
                print(message.content[0].text.value)
                break
    else:
        print(f"Run ended with status: {run.status}")

if __name__ == "__main__":
    main()
