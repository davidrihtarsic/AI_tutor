// Focus the message input field when the page loads
window.onload = function() {
    document.getElementById('studentNameInput').focus();
    checkMessageInputStatus();  // Check the message input status on page load
};

let studentId = null; // Global variable for student ID
let studentName = null; // Global variable for student name
let isNameLocked = false;  // Flag to check if the name input has been locked

let isStudentLoggedIn = false;  // Flag to check if the student is logged in

async function checkMessageInputStatus() {
    const response = await fetch('/get_message_input_status');
    const data = await response.json();
    const messageInput = document.getElementById('messageInput');
    const sendButton = document.getElementById('sendButton');
    const loginButton = document.getElementById('loginButton');
    if (data.enabled && isStudentLoggedIn) {
        loginButton.setAttribute('disabled', 'true');
        messageInput.removeAttribute('disabled');
        sendButton.removeAttribute('disabled');
    } else if (data.enabled && !isStudentLoggedIn) {
        loginButton.removeAttribute('disabled');
        messageInput.setAttribute('disabled', 'true');
        sendButton.setAttribute('disabled', 'true');
    } else {
        loginButton.setAttribute('disabled', 'true');
        messageInput.setAttribute('disabled', 'true');
        sendButton.setAttribute('disabled', 'true');
    }
}
setInterval(checkMessageInputStatus, 5000);

function login() {
    studentName = document.getElementById('studentNameInput').value;
    studentId = document.getElementById('studentIdInput').value || Math.floor(Math.random() * 10000000); // Generate random ID if empty

    // Disable the input fields and login button
    document.getElementById('studentNameInput').disabled = true;
    document.getElementById('studentIdInput').disabled = true;
    document.getElementById('loginButton').disabled = true;

    isStudentLoggedIn = true;  // Set the flag to true

    console.log(`Student Name: ${studentName}, Student ID: ${studentId}`);

    // Load previous conversations if they exist
    loadPreviousConversations(studentId);

    // Check the message input status again after login
    checkMessageInputStatus();
}

function loadPreviousConversations(studentId) {
    fetch(`/api/conversations?student_id=${studentId}`)
        .then(response => response.json())
        .then(data => {
            const chatBox = document.getElementById('chatBox');
            chatBox.innerHTML = '';  // Clear existing messages

            if (data.messages) {
                data.messages.forEach(msg => {
                    chatBox.innerHTML += `<div class="student-message"><strong>${data.student_name}:</strong> ${msg.question}</div>`;
                    // Remove surrounding single quotes before parsing
                    const response = msg.response.slice(1, -1).replace(/\\n/g, '\n');
                    chatBox.innerHTML += `<div class="gpt-message">${marked.parse(response)}</div>`;
                });
                chatBox.scrollTop = chatBox.scrollHeight;  // Scroll to bottom after loading messages
            }
        })
        .catch(error => {
            console.error("Error loading previous conversations:", error);
        });
}

function sendMessage() {
    const studentName = document.getElementById('studentNameInput').value || 'You';  // Default
    // Lock the student's name input field if it's not already locked
    if (!isNameLocked) {
        studentNameInput.disabled = true;  // Disable the name input field
        isNameLocked = true;               // Set the flag to true
    }
    
    const message = document.getElementById('messageInput').value;
    console.log("Message sent:", message);  // Debugging to check message value
    document.getElementById('messageInput').value = '';
    // Focus the message input field after sending
    document.getElementById('messageInput').focus();  // Automatically focus the input
    
    const chatBox = document.getElementById('chatBox');
    chatBox.innerHTML += `<div class="student-message"><strong>${studentName}:</strong> ${message}</div>`;
    chatBox.scrollTop = chatBox.scrollHeight;  // Scroll to bottom after adding the message

    // Create a new message div to display the GPT response
    const gptMessageDiv = document.createElement('div');
    gptMessageDiv.className = 'gpt-message';
    chatBox.appendChild(gptMessageDiv);

    let fullResponse = '';  // Accumulate the full response

    // Open an EventSource to receive the response from the server
    const eventSource = new EventSource('/chat_stream?message=' + encodeURIComponent(message) + '&student_id=' + studentId + '&student_name=' + studentName);
    
    // Open an EventSource to receive the response from the server
    //const eventSource = new EventSource(`/chat_stream?message=${encodeURIComponent(message)}&student_id=${studentId}&student_name=${encodeURIComponent(studentName)}`);

    eventSource.onmessage = function(event) {
        console.log("Streaming data received:", event.data);  // Debugging received data
        // Accumulate the response and handle newlines correctly
        fullResponse += event.data.slice(1, -1);
        // Optionally, display raw text during streaming
        // fullResponse = fullResponse.replace(/\\n\\n/g, '<br>');
        fullResponse = fullResponse.replace(/\\n/g, '<br>');
        gptMessageDiv.innerHTML = fullResponse;  // Temporarily display the text while streaming
        chatBox.scrollTop = chatBox.scrollHeight;  // Scroll to bottom
    };

    eventSource.onerror = function(err) {
        console.error("EventSource failed: ", err);
        chatBox.innerHTML += `<div class="error-message"><strong>Error:</strong> There was a problem receiving the response.</div>`;
        eventSource.close();  // Close the EventSource on error
    };
    
    eventSource.addEventListener('end', function() {
        // Overwrite fullResponse with the last chunk sent, which contains the complete response
        fullResponse = event.data;  // Overwrite fullResponse with the last complete response
        console.log("Full response:", fullResponse);  // Debugging full response

        // Replace escaped newlines (\\n) with actual newlines (\n)
        let parsedResponse = fullResponse.replace(/\\n/g, '\n');

        // Strip leading and trailing quotes (if present)
        parsedResponse = parsedResponse.slice(1, -1);

        // Apply Markdown parsing after fixing the string
        gptMessageDiv.innerHTML = marked.parse(parsedResponse);  // Apply Markdown parsing to the final response
        hljs.highlightAll();
        chatBox.scrollTop = chatBox.scrollHeight;  // Scroll to bottom
        eventSource.close();  // Close the connection
    });
}

// Add an event listener to handle the message from the admin page
window.addEventListener('message', function(event) {
    if (event.data === 'refreshMessageInputStatus') {
        checkMessageInputStatus();
    }
});
