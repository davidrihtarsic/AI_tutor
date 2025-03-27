// Store the IDs of conversations and answers that are open (visible)
let openAnswers = new Set();
let openQuestions = new Set();
let selectedAssistant = 'elora_1'; // Default assistant

function fetchConversations() {
    fetch(`/api/conversations?assistant_id=${selectedAssistant}`)
        .then(response => response.json())
        .then(data => {
            const conversationsDiv = document.getElementById('conversations');
            conversationsDiv.innerHTML = '';  // Clear existing conversations

            for (const studentId in data) {
                if (data.hasOwnProperty(studentId)) {
                    const convo = data[studentId];
                    const convoDiv = document.createElement('div');
                    convoDiv.className = 'conversation';

                    // Display Student ID and Name at the top
                    const studentInfo = document.createElement('p');
                    studentInfo.className = 'student-name';
                    studentInfo.textContent = `${convo.student_name || 'Unknown'} [${studentId}]`;
                    studentInfo.onclick = function() {
                        toggleQuestions(studentId);
                    };
                    convoDiv.appendChild(studentInfo);

                    // Create a div for the questions, hidden by default
                    const questionsDiv = document.createElement('div');
                    questionsDiv.className = 'questions';
                    questionsDiv.id = `questions_${studentId}`;
                    questionsDiv.style.display = openQuestions.has(studentId) ? 'block' : 'none';  // Keep open if it was already open

                    // Loop through the student's questions and answers
                    convo.messages.forEach((msg, index) => {
                        const uniqueId = `${studentId}_${index}`; // Unique ID for each Q&A

                        // Create the question link
                        const questionDiv = document.createElement('div');
                        questionDiv.className = 'question-wrapper';
                        
                        const questionLink = document.createElement('a');
                        questionLink.href = 'javascript:void(0)';
                        questionLink.className = 'show-answer';
                        questionLink.textContent = `${msg.question}`;
                        questionLink.onclick = function() {
                            toggleAnswer(uniqueId);
                        };

                        questionDiv.appendChild(questionLink);
                        questionsDiv.appendChild(questionDiv);  // Append question in a new div

                        // Create a div for the answer, hidden by default
                        const answerDiv = document.createElement('div');
                        answerDiv.className = 'answer';
                        answerDiv.id = uniqueId;
                        answerDiv.style.display = openAnswers.has(uniqueId) ? 'block' : 'none';  // Keep open if it was already open

                        // Set the full response (replace \n with <br> for multiline)
                        const fullResponse = msg.response.slice(1, -1).replace(/\\n/g, '\n');
                        answerDiv.innerHTML = marked.parse(fullResponse);

                        // Add a [close] link at the bottom of the answer
                        const closeLink = document.createElement('a');
                        closeLink.href = 'javascript:void(0)';
                        closeLink.textContent = '[close]';
                        closeLink.className = 'close-answer';
                        closeLink.onclick = function() {
                            toggleAnswer(uniqueId);  // Close the answer when clicked
                        };
                        answerDiv.appendChild(closeLink);

                        // Highlight newly added code blocks only
                        answerDiv.querySelectorAll('pre code').forEach((block) => {
                            hljs.highlightElement(block);
                        });
                        questionsDiv.appendChild(answerDiv);
                    });

                    convoDiv.appendChild(questionsDiv);
                    conversationsDiv.appendChild(convoDiv);
                }
            }
        })
        .catch(error => {
            console.error("Error fetching conversations:", error);
        });
}

// Function to toggle the visibility of the questions
function toggleQuestions(studentId) {
    const questionsDiv = document.getElementById(`questions_${studentId}`);

    if (questionsDiv.style.display === 'none') {
        questionsDiv.style.display = 'block';
        openQuestions.add(studentId);  // Remember that these questions are open
    } else {
        questionsDiv.style.display = 'none';
        openQuestions.delete(studentId);  // Remove it from the open set
    }
}

// Function to toggle the visibility of the answer
function toggleAnswer(uniqueId) {
    const answerDiv = document.getElementById(uniqueId);

    if (answerDiv.style.display === 'none') {
        answerDiv.style.display = 'block';
        openAnswers.add(uniqueId);  // Remember that this answer is open
    } else {
        answerDiv.style.display = 'none';
        openAnswers.delete(uniqueId);  // Remove it from the open set
    }
}

// Function to handle assistant selection change
function changeAssistant() {
    const assistantSelect = document.getElementById('assistantSelect');
    const assistantName = assistantSelect.value;
    fetch(`/api/set_assistant?name=${assistantName}`)
        .then(response => response.json())
        .then(data => {
            selectedAssistant = data.assistant_id;
            fetchConversations(); // Fetch conversations for the selected assistant
        })
        .catch(error => {
            console.error("Error setting assistant:", error);
        });
}

document.addEventListener('DOMContentLoaded', function() {
    const toggleSlider = document.getElementById('toggleSlider');

    toggleSlider.addEventListener('click', async function() {
        this.classList.toggle('active');
        await fetch('/toggle_message_input_status', { method: 'POST' });
        notifyIndexPage(); // Notify the index page about the status change
    });

    document.getElementById('conversationSelect').addEventListener('change', function() {
        loadConversations(this.value);
    });

    // Call fetchConversations on page load
    fetchConversations();
    const assistantSelect = document.getElementById('assistantSelect');
    assistantSelect.addEventListener('change', changeAssistant);
});

async function loadConversations(file) {
    await fetch(`/load_conversations?file=${file}`, { method: 'POST' });
    fetchConversations(); // Fetch the updated conversations without reloading the page
}

function notifyIndexPage() {
    if (window.opener) {
        window.opener.postMessage('refreshMessageInputStatus', '*');
    }
}

// Optionally, you can auto-refresh the data every 10 seconds
setInterval(fetchConversations, 10000);
