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
# Naloži konfiguracijo
config = load_config()
client = OpenAI(api_key=config["api_key"])
ASSISTANT_ID = config["ai_elora_2"]

# Path to the JSON file where conversations will be saved
#CONVERSATIONS_FILE = 'conversations.json'
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
    print(f"{student_id} ({student_name}): {user_input}")

    try:
        # Check if there is an existing thread for the student
        if student_id not in conversations:
            # If not, create a new thread for the student
            thread = client.beta.threads.create(
                messages=[ { "role":"user", "content":user_input } ],
            )  
            thread_id = thread.id
            # Add the student name and thread ID to the conversations dictionary
            conversations[student_id] = {
                'student_name': student_name,  # Store the student's name
                'thread_id': thread_id,
                'messages': []
            }
            if debug:
                print(f"Creating thread_id: {thread_id} for student_id: {student_id}")
        else:
            # Reuse the existing thread
            thread_id = conversations[student_id]['thread_id']
            message = client.beta.threads.messages.create(
                thread_id=thread_id,
                role="user",
                content=user_input
            )
            if debug:
                print(f"Using existing thread_id: {thread_id} for student_id: {student_id}")
                print(f"Message added to thread: {message}")

        def generate_response():
            gpt_response = ""
            # Stream the response from the assistant
            if debug:
                print(f"Using thread_id: {thread_id} for student_id: {student_id}")
                print(f"Assistant ID: {ASSISTANT_ID}")
            with client.beta.threads.runs.stream(
                thread_id=thread_id,
                assistant_id=ASSISTANT_ID,
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
            #print(conversations)
            # Save conversations after each update
            if len(gpt_response)<5:
                print(stream)
            save_conversations()

            # After the stream ends, send the accumulated full response as one final chunk for Markdown parsing
            yield f"event: end\ndata: {repr(gpt_response)}\n\n"

        return Response(generate_response(), mimetype='text/event-stream')

    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/api/set_assistant')
def set_assistant():
    assistant_name = request.args.get('name')
    global ASSISTANT_ID
    ASSISTANT_ID = config[assistant_name]
    return jsonify({'assistant_id': ASSISTANT_ID})

@app.route('/admin')
def admin():
    assistants = {key: value for key, value in config.items() if key.startswith('ai_')}
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
