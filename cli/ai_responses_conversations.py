#!/usr/bin/env python3
import os
import json
from openai import OpenAI

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# 🧠 Navodila asistenta
AI_AGENT_INSTRUCTIONS = """
Ti si AI pomočnik učitelju tehnike in tehnologije v osnovni šoli.
Tvoja naloga je pomagati pri pripravi učnih ur, pri iskanju idej za učne dejavnosti,
ter pri oblikovanju preprostih razlag za učence. 
"""

# 🔁 Če želiš nadaljevati obstoječi pogovor, sem vnesi npr. "conv_abc123..."
CONVERSATION_ID = ""
CONVERSATIONS_FILE = "conversations.json"


def load_conversations():
    """Naloži pogovore iz datoteke, če obstaja."""
    if os.path.exists(CONVERSATIONS_FILE):
        with open(CONVERSATIONS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_conversations(conversations):
    """Shrani pogovore v datoteko."""
    with open(CONVERSATIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(conversations, f, indent=4, ensure_ascii=False)


def get_conversation(conversations):
    """Preveri, ali obstaja pogovor, sicer ustvari novega."""
    global CONVERSATION_ID
    if not CONVERSATION_ID or CONVERSATION_ID not in conversations:
        conv = client.conversations.create()
        CONVERSATION_ID = conv.id
        print(f"[Ustvarjen nov ID pogovora]: {CONVERSATION_ID}")
        conversations[CONVERSATION_ID] = {"messages": []}
        save_conversations(conversations)
    else:
        print(f"[Nadaljujem pogovor]: {CONVERSATION_ID}")
    return conversations[CONVERSATION_ID]


def start_chat():
    conversations = load_conversations()
    conversation = get_conversation(conversations)

    print("\nZačni pogovor (vpiši 'exit' za izhod)\n")

    # Naloži prejšnje pogovore
    if conversation["messages"]:
        print("📜 Prejšnji pogovori:")
        for msg in conversation["messages"]:
            print(f"👤 {msg['question']}")
            print(f"🧠  {msg['response']}\n")

    while True:
        user_input = input("👤 Ti: ").strip()
        if user_input.lower() in ["exit", "quit"]:
            print("🔚 Pogovor zaključen.")
            break

        response = client.responses.create(
            model="gpt-4.1-mini",
            conversation=CONVERSATION_ID,
            input=[
                {"role": "system", "content": AI_AGENT_INSTRUCTIONS},
                {"role": "user", "content": user_input},
            ],
            tools=[
               # {
               #     "type": "file_search",
               #     "vector_store_ids": ["vs_68f0014fe51c819184b6c36568f1ade0"],
               # }
            ],
        )

        answer = response.output_text
        print(f"🧠 Asistent: {answer}\n")

        # Shrani vprašanje in odgovor v datoteko
        conversation["messages"].append({
            "question": user_input,
            "response": answer
        })
        conversations[CONVERSATION_ID] = conversation
        save_conversations(conversations)


if __name__ == "__main__":
    start_chat()

