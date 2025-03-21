// Import HTMX and extensions
import htmx from 'htmx.org';
import 'htmx-ext-form-json';
import 'htmx-ext-sse';
import hljs from 'highlight.js';
// import Bulma from "@vizuaalog/bulmajs";
import Dropdown from "@vizuaalog/bulmajs/src/plugins/dropdown";

import {initializeEditor} from './prosemirror';

// Import custom handlers
import './shutdown-handler';


// Initialize application
document.addEventListener('DOMContentLoaded', () => {
  console.log('BikeShed application initialized');

  // Ensure SSE extension is properly initialized
  if (typeof htmx !== 'undefined') {
    console.log('HTMX loaded successfully');

    // Log SSE connection events
    document.body.addEventListener('htmx:sseOpen', function(event) {
      console.log('SSE Connected');
    });

  } else {
    console.error('HTMX not loaded properly');
  }

  // Initialize theme from localStorage
  initializeTheme();
  setupThemeToggle();
});

// Function to initialize theme
function initializeTheme() {
  const savedTheme = localStorage.getItem('theme');
  if (savedTheme) {
    document.documentElement.setAttribute('data-theme', savedTheme);
  }
}

// Setup theme toggle when navbar is loaded and highlight code blocks
document.body.addEventListener('htmx:afterSettle', function(event) {

  // if (event.detail.elt.querySelector && event.detail.elt.querySelector('#editor')) {
  //   initializeEditor();
  // }

  // Apply syntax highlighting to any new code blocks
  // if (event.detail.elt.querySelector && event.detail.elt.querySelector('pre code')) {
  //   for (const elem of event.detail.elt.querySelectorAll('pre code')) {
  //     hljs.highlightElement(elem);
  //   }
  // }

  // Activate bulma JS behaviors on newly added elements
  if (event.detail.elt.querySelector && event.detail.elt.querySelector('.dropdown')) {
    Dropdown.parseDocument();
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

