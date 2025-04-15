#! /bin/python3

from flask import Flask, Response, request, jsonify, render_template
from openai import OpenAI  # Replace with the actual OpenAI client library you're using
import json  # To handle JSON file operations
import os  # To check if the JSON file exists
import glob

app = Flask(__name__)

debug = True

# Set up your OpenAI client with the API key
def load_config(file_path="config/config.json"):
    try:
        with open(file_path, 'r') as file:
            config = json.load(file)
        print("Configuration loaded successfully.")
        return config
    except FileNotFoundError:
        print("Error: config.json not found. Please ensure the file exists.")
        raise
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON: {e}")
        raise

# Save updated configuration to config.json
def save_config(file_path="config/config.json"):
    try:
        with open(file_path, 'w', encoding='utf-8') as file:
            json.dump(config, file, ensure_ascii=False, indent=4)
            print("Configuration saved successfully.")
    except Exception as e:
        print(f"Error saving configuration: {e}")
        raise

# Load configuration
config = load_config()

# Use the first API key and assistant ID as defaults
default_api_key_name = next(iter(config["api_keys"]))
assistant_name = next(iter(config["assistants"]))
client = OpenAI(api_key=config["api_keys"][default_api_key_name])

# Path to the JSON file where conversations will be saved
CONVERSATIONS_DIR = 'conversations'

# Store conversations (can be changed to use a database)
conversations = {}

# Load conversations from a specific file
def load_conversations(file_path):
    global conversations
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as file:
            conversations = json.load(file)
            print(f"Conversations loaded from {file_path}.")
    else:
        print(f"No saved conversations found in {file_path}. Starting fresh.")

# Save conversations to the selected file
def save_conversations():
    global selected_conversation_file
    file_path = os.path.join(CONVERSATIONS_DIR, selected_conversation_file)
    with open(file_path, 'w', encoding='utf-8') as file:
        json.dump(conversations, file, ensure_ascii=False, indent=4)
        print(f"Conversations saved to {file_path}.")

# Global variable to store the status of the message input field
message_input_enabled = False

# Global variable to store the selected conversation file
selected_conversation_file = 'default.json'

@app.route('/get_message_input_status')
def get_message_input_status():
    global message_input_enabled
    return jsonify({'enabled': message_input_enabled})

@app.route('/toggle_message_input_status', methods=['POST'])
def toggle_message_input_status():
    global message_input_enabled
    message_input_enabled = not message_input_enabled
    return '', 204

# Route for the main chat page for students
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/chat_stream')
def chat_stream():
    user_input = request.args.get('message')
    student_id = request.args.get('student_id')
    student_name = request.args.get('student_name')  # Get the student's name
    if debug:
        print(f"{student_name} ({student_id}) using assistant {assistant_name}: {user_input}")

    try:
        # Check if the student exists in conversations
        if student_id not in conversations:
            # Create a new student entry in conversations
            conversations[student_id] = {
                'student_name': student_name,
                'thread_id': "",
                'messages': []
            }
            if debug:
                print(f"Created new student entry for {student_name} ({student_id}).")

        # Get the assistant configuration
        assistant_config = config["assistants"].get(assistant_name)
        if not assistant_config:
            return jsonify({'error': f"No assistant configuration found for {assistant_name}."}), 400

        assistant_id = assistant_config.get("openai_assistant_id")
        assistant_instructions = assistant_config.get("instructions", "")
        if debug:
            print(f"\nAssistant ID: {assistant_id},\nInstructions: {assistant_instructions}")
        # Check if openai_assistant_id exists, if not, create an assistant
        if not assistant_id:
            if debug:
                print(f"Creating new assistant for {assistant_name}...")
            if assistant_instructions:
                # Create the assistant with the provided instructions
                if debug:
                    print(f"Creating assistant with instructions: {assistant_instructions}")
                assistant = client.beta.assistants.create(
                    name=assistant_name,
                    instructions=assistant_instructions,
                    model="gpt-4.1-nano",
                )
                assistant_id = assistant.id
                assistant_config["openai_assistant_id"] = assistant_id
                save_config()  # Save the updated assistant ID to config.json
                if debug:
                    print(f"Created new assistant for {assistant_name} with ID: {assistant_id}")
            else:
                return jsonify({'error': 'No openai_assistant_id and no instructions provided.'}), 400
        else:
            if debug:
                print(f"Using existing assistant_id: {assistant_id} for assistant_name: {assistant_name}")

        # Check if a thread exists for the student, if not, create one
        thread_id = conversations[student_id].get('thread_id')
        if debug:
            print(f"Thread ID for student {student_id}: {thread_id}")
        
        if not thread_id:  # Check for falsy values like None, "", or missing keys
            thread = client.beta.threads.create(
                messages=[{"role": "user", "content": user_input}],
            )
            conversations[student_id]['thread_id'] = thread.id
            if debug:
                print(f"Created new thread for student_id: {student_id} with thread_id: {thread.id}")
        else:
            # Append the user message to the existing thread
            if debug:
                print(f"Appending message to existing thread for student_id: {student_id}")
            thread_id = conversations[student_id]['thread_id']
            msg = client.beta.threads.messages.create(
                thread_id=thread_id,
                role="user",
                content=user_input
            )
            if debug:
                print(f"Appended message to thread {thread_id}: {msg}")
        
        def generate_response():
            gpt_response = ""
            thread_id = conversations[student_id]['thread_id']

            # Stream the response from the assistant
            if debug:
                print(f"Using thread_id: {thread_id} for student_id: {student_id}")
                print(f"Assistant ID: {assistant_id}")
            with client.beta.threads.runs.stream(
                thread_id=thread_id,
                assistant_id=assistant_id,
                timeout=30
            ) as stream:
                for text_delta in stream.text_deltas:
                    gpt_response += text_delta  # Accumulate the full response
                    if debug:
                        print(text_delta, end='', flush=True)  # Print directly to the terminal continuously
                    # Send chunks of the response to the frontend immediately as they are streamed
                    yield f"data: {repr(text_delta)}\n\n"

            # Store the question and response in the conversations dictionary
            conversations[student_id]['messages'].append({
                'question': user_input,
                'response': f"{repr(gpt_response)}"
            })

            # Save conversations after each update
            save_conversations()

            # After the stream ends, send the accumulated full response as one final chunk for Markdown parsing
            yield f"event: end\ndata: {repr(gpt_response)}\n\n"

        return Response(generate_response(), mimetype='text/event-stream')

    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/api/set_assistant')
def set_assistant():
    global assistant_name 
    assistant_name = request.args.get('name')
    if assistant_name in config["assistants"]:
        assistant = config["assistants"][assistant_name]
        assistant_id = assistant["openai_assistant_id"] if isinstance(assistant, dict) else assistant
    if debug:
        print(f"Assistant set to: {assistant_name} with ID: {assistant_id}")
    return jsonify({'assistant_id': assistant_id})

@app.route('/admin')
def admin():
    assistants = {
        key: (value["openai_assistant_id"] if isinstance(value, dict) else value)
        for key, value in config["assistants"].items()
    }
    conversation_files = [os.path.basename(f) for f in glob.glob(os.path.join(CONVERSATIONS_DIR, '*.json'))]
    return render_template('admin.html', assistants=assistants, conversation_files=conversation_files, selected_conversation_file=selected_conversation_file)

@app.route('/load_conversations', methods=['POST'])
def load_conversations_route():
    global message_input_enabled    # Testing
    message_input_enabled = False   # Testing
    global selected_conversation_file
    file = request.args.get('file')
    file_path = os.path.join(CONVERSATIONS_DIR, file)
    load_conversations(file_path)
    selected_conversation_file = file
    return '', 204

@app.route('/api/conversations')
def get_conversations():
    student_id = request.args.get('student_id')
    if student_id:
        # Return the conversation for the specific student ID
        return jsonify(conversations.get(student_id, {}))
    else:
        # Return all conversations
        return jsonify(conversations)

if __name__ == '__main__':
    # Load the default conversations from file when the server starts
    load_conversations(os.path.join(CONVERSATIONS_DIR, 'default.json'))
    app.run(host='0.0.0.0', port=5000)
