// Import Bulma
import Bulma from '@vizuaalog/bulmajs';

// Import HTMX and extensions
import htmx from 'htmx.org';
import 'htmx-ext-sse';


// Import custom handlers
import './shutdown-handler.js';

// Initialize application
document.addEventListener('DOMContentLoaded', () => {
  console.log('Flibberflow application initialized');
  
  // Ensure SSE extension is properly initialized
  if (typeof htmx !== 'undefined') {
    console.log('HTMX loaded successfully');
    
    // Log SSE connection events
    document.body.addEventListener('sse:connected', function(event) {
      console.log('SSE Connected:', event.detail);
    });

    // Log specific update events
    ['session_update', 'form_update', 'sidebar_update', 'drawer_update'].forEach(eventName => {
      document.body.addEventListener(`sse:${eventName}`, function(event) {
        console.log(`SSE ${eventName}:`, event.detail);
      });
    });
  } else {
    console.error('HTMX not loaded properly');
  }

  // Initialize theme from localStorage
  initializeTheme();
});

// Function to initialize theme
function initializeTheme() {
  const savedTheme = localStorage.getItem('theme');
  if (savedTheme) {
    document.documentElement.setAttribute('data-theme', savedTheme);
  }
}

// Setup theme toggle when navbar is loaded
document.body.addEventListener('htmx:afterSettle', function(event) {
  // Only proceed if the loaded content contains the theme toggle
  if (event.detail.elt.querySelector && event.detail.elt.querySelector('.theme-toggle')) {
    setupThemeToggle();
  }


});

// Function to set up theme toggle
function setupThemeToggle() {
  const themeToggle = document.querySelector('.theme-toggle');
  if (!themeToggle) return;
  
  // Remove any existing event listeners by cloning and replacing
  const newThemeToggle = themeToggle.cloneNode(true);
  themeToggle.parentNode.replaceChild(newThemeToggle, themeToggle);
  
  // Add click event listener
  newThemeToggle.addEventListener('click', function(e) {
    e.preventDefault();

    const html = document.documentElement;
    const currentTheme = html.getAttribute('data-theme') || 'light';
    const newTheme = currentTheme === 'dark' ? 'light' : 'dark';

    // Update the theme
    html.setAttribute('data-theme', newTheme);

    // Update the button text and icon
    const icon = this.querySelector('i');
    const text = this.querySelector('.theme-text');

    if (newTheme === 'dark') {
      icon.classList.remove('fa-moon');
      icon.classList.add('fa-sun');
      text.textContent = 'Dark Mode';
    } else {
      icon.classList.remove('fa-sun');
      icon.classList.add('fa-moon');
      text.textContent = 'Light Mode';
    }

    // Store the preference in localStorage
    localStorage.setItem('theme', newTheme);
  });

  // Update button to match current theme
  updateThemeToggleAppearance(newThemeToggle);
}

// Function to update theme toggle appearance
function updateThemeToggleAppearance(themeToggle) {
  if (!themeToggle) {
    themeToggle = document.querySelector('.theme-toggle');
    if (!themeToggle) return;
  }
  
  const currentTheme = document.documentElement.getAttribute('data-theme') || 'light';
  const icon = themeToggle.querySelector('i');
  const text = themeToggle.querySelector('.theme-text');
  
  if (currentTheme === 'dark') {
    icon.classList.remove('fa-moon');
    icon.classList.add('fa-sun');
    text.textContent = 'Dark Mode';
  } else {
    icon.classList.remove('fa-sun');
    icon.classList.add('fa-moon');
    text.textContent = 'Light Mode';
  }
}
