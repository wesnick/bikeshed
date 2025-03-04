/**
 * Chat functionality
 */

// Timer variables
let timerInterval;
let startTime;

export function initChat() {
  // Add event listeners for utility buttons
  document.querySelector('.button[title="Clear chat"]')?.addEventListener('click', clearChat);
  
  // Initialize any other chat-related functionality
}

export function startTimer() {
  // Clear any existing timer
  if (timerInterval) {
    clearInterval(timerInterval);
  }
  
  const timerElement = document.getElementById('response-timer');
  timerElement.classList.remove('is-hidden');
  startTime = Date.now();
  
  timerInterval = setInterval(() => {
    const elapsedTime = (Date.now() - startTime) / 1000;
    timerElement.textContent = elapsedTime.toFixed(1) + 's';
  }, 100);
}

export function stopTimer() {
  if (timerInterval) {
    clearInterval(timerInterval);
    timerInterval = null;
  }
}

function clearChat() {
  const chatMessages = document.getElementById('chat-messages');
  // Keep only the welcome message
  chatMessages.innerHTML = `
    <div class="welcome-message">
      <p>Welcome to Flibberflow Chat! Start a conversation below.</p>
    </div>
  `;
}
