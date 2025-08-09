"""
AI_tutor CLI - Navodila za uporabo
-----------------------------------

Osnovna uporaba:
  python3 ai.py [assistant_name] "vaše vprašanje"
  ./cli/ai.py [assistant_name] "vaše vprašanje"

Primeri:
  ./cli/ai.py ArchLinuxAssistant "Kako izpišem vsebino direktorija?"
  ./cli/ai.py Fixy "Zakaj robot ne deluje?"
  ./cli/ai.py TiTWriter "Napiši strokovni povzetek tega besedila."

Uporaba s kontekstom iz stdin (npr. iz datoteke ali pipe):
  cat napaka.log | ./cli/ai.py ArchLinuxAssistant "Zakaj je prišlo do te napake?"
  ./cli/ai.py TiTWriter "Naredi povzetek" < besedilo.txt

Uporaba s kontekstom iz označenega besedila (X11 PRIMARY selection, Linux):
  ./cli/ai.py ArchLinuxAssistant --clip "Kaj pomeni ta ukaz?"
  # Če želiš brati iz CLIPBOARD (Ctrl+C), spremeni 'primary' v 'clipboard' v kodi.

Če asistenta ne navedeš, se uporabi privzeti (ArchLinuxAssistant):
  ./cli/ai.py "Kaj je GPT?"

"""
#!/usr/bin/env python3
import sys
import json
import os

import time
from openai import OpenAI
import threading

CONV_PATH = os.path.join(os.path.dirname(__file__), "../conversations/conv.json")

def load_threads():
    if not os.path.exists(CONV_PATH):
        return {}
    with open(CONV_PATH, "r") as f:
        try:
            return json.load(f)
        except Exception:
            return {}

def save_threads(threads):
    with open(CONV_PATH, "w") as f:
        json.dump(threads, f, indent=4)

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "../config/config.json")

def load_config():
    with open(CONFIG_PATH, "r") as f:
        return json.load(f)

def get_api_key_and_assistant_id(config, assistant_name="ArchLinuxAssistant"):
    api_key = config["api_keys"]["default_key"]
    assistant_id = config["assistants"][assistant_name]["openai_assistant_id"]
    return api_key, assistant_id

def main():

    # Preveri, če je stdin ne-prazen (npr. echo ... | ./cli/ai.py ... ali < file)
    import select
    stdin_context = None
    if not sys.stdin.isatty():
        try:
            if select.select([sys.stdin], [], [], 0.0)[0]:
                stdin_context = sys.stdin.read().strip()
        except Exception:
            pass

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

    # Če je stdin_context, ga dodaj kot kontekst
    if stdin_context:
        user_input = f"[Kontekst]\n{stdin_context}\n\n[Navodilo]\n{user_input}"

    api_key, assistant_id = get_api_key_and_assistant_id(config, assistant_name)
    client = OpenAI(api_key=api_key)

    # Naloži ali ustvari thread_id za tega asistenta

    threads = load_threads()
    thread_entry = threads.get(assistant_id)
    # thread_entry je lahko dict (pravilna oblika), ali string (stara oblika)
    if isinstance(thread_entry, dict):
        thread_id = thread_entry.get("thread_id")
    elif isinstance(thread_entry, str):
        thread_id = thread_entry
        # Migriraj na novo obliko
        threads[assistant_id] = {
            "student_name": assistant_name,
            "thread_id": thread_id,
            "messages": []
        }
        save_threads(threads)
    else:
        thread_id = None

    if not thread_id:
        thread = client.beta.threads.create()
        thread_id = thread.id
        threads[assistant_id] = {
            "student_name": assistant_name,
            "thread_id": thread_id,
            "messages": []
        }
        save_threads(threads)
        print(f"Created new thread with ID: {thread_id}")

    # Pošlji sporočilo v obstoječi ali nov thread
    client.beta.threads.messages.create(
        thread_id=thread_id,
        role="user",
        content=user_input,
    )
    print(f"Sending message to thread:\n {user_input}"),

    run = client.beta.threads.runs.create(
        thread_id=thread_id,
        assistant_id=assistant_id,
    )

    while run.status not in {"completed", "failed", "cancelled", "expired"}:
        time.sleep(1)
        run = client.beta.threads.runs.retrieve(
            thread_id=thread_id,
            run_id=run.id,
        )

    if run.status == "completed":
        messages = client.beta.threads.messages.list(thread_id=thread_id)
        for message in messages.data:
            if message.role == "assistant" and message.content:
                print(message.content[0].text.value)
                break
    else:
        print(f"Run ended with status: {run.status}")

if __name__ == "__main__":
    main()
