#!/usr/bin/env python3
import os
from openai import OpenAI

# 🔧 Nastavi svoj API ključ
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# 🔁 Če želiš ohraniti isti pogovor, vnesi tu ID, npr. "conv_abc123..."
CONVERSATION_ID = "conv_68f00d96a8d8819698235b1ec9ae16df08246b7a10722d12"

# 🧠 Navodila ai agenta
AI_AGENT_INSTRUCTIONS = """
Ti si AI pomočnik učitelju tehnike in tehnologije v osnovni šoli.
Tvoja naloga je pomagati pri pripravi učnih ur, pri iskanju idej za učne dejavnosti,
ter pri oblikovanju preprostih razlag za učence.
"""

def get_conversation_id():
    """Ustvari nov pogovor, če ID še ni določen."""
    global CONVERSATION_ID
    if not CONVERSATION_ID:
        conv = client.conversations.create()
        CONVERSATION_ID = conv.id
        print(f"[Ustvarjen nov ID pogovora]: {CONVERSATION_ID}")
    else:
        print(f"[Uporablja se obstoječi ID pogovora]: {CONVERSATION_ID}")
    return CONVERSATION_ID

def start_chat():
    conversation_id = get_conversation_id()
    print("\nZačni pogovor (vpiši 'exit' za izhod)\n")

    while True:
        user_input = input("👤 Ti: ").strip()
        if user_input.lower() in ["exit", "quit"]:
            print("🔚 Pogovor zaključen.")
            break

        response = client.responses.create(
            model="gpt-5-nano",
            conversation=conversation_id,
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

        print(f"\n🧠 Asistent: {response.output_text}\n")

if __name__ == "__main__":
    start_chat()
