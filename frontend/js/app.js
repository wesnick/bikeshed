// Import HTMX and extensions
import htmx from 'htmx.org';
import 'htmx-ext-form-json';
import 'htmx-ext-sse';
import hljs from 'highlight.js';


import {initializeEditor} from './components/prosemirror';
import {initializePanelFilters} from './components/panel_filter';
import {initializeModal} from "./components/modal";
import {initializeDropdowns} from "./components/dropdown";
import {setupThemeToggle} from "./components/theme_toggle";
import {initializeDropzone} from "./components/dropzone";
import {initializeTagAutocomplete} from "./components/tags";
import {handleSPARefresh, shutdownHandler} from './components/shutdown-handler';


// Initialize application
document.addEventListener('DOMContentLoaded', () => {

  // Ensure SSE extension is properly initialized
  if (typeof htmx !== 'undefined') {
    handleSPARefresh()

    console.log('BikeShed application initialized');

    // Log SSE connection events
    document.body.addEventListener('htmx:sseOpen', function (event) {
      console.log('SSE Connected');
    });

    document.body.addEventListener('htmx:sseClose', function (event) {
      shutdownHandler(event)
    });

    // Listen for history changes and dispatch route.changed event
    document.body.addEventListener('htmx:pushedIntoHistory', function (event) {
      document.body.dispatchEvent(new Event('route.updated'));
    });

  } else {
    console.error('HTMX not loaded properly');
  }

  // Initialize theme from localStorage
  initializeTheme();
  setupThemeToggle();
  initializeModal()
});

// Function to initialize theme
function initializeTheme() {
  const savedTheme = localStorage.getItem('theme');
  if (savedTheme) {
    document.documentElement.setAttribute('data-theme', savedTheme);
  }
}

// Setup theme toggle when navbar is loaded and highlight code blocks
document.body.addEventListener('htmx:afterSettle', function (event) {

  if (event.detail.elt.id === 'messages-container') {
    const messagesContainer = document.getElementById('dashboard-top');
    if (messagesContainer) {
      messagesContainer.scrollTo({
        top: messagesContainer.scrollHeight - 200,
        behavior: 'smooth'
      });
    }
  }

  // Modal Support
  const modalContent = document.getElementById('modal-container')?.querySelector('.modal-content');
  if (modalContent && event.detail.target === modalContent) {
    const modal = document.getElementById('modal-container');
    if (modal) {
      modal.classList.add('is-active');
      document.documentElement.classList.add('is-clipped'); // Add clipping to HTML tag
    }
  }

  // Editor support
  // if (event.detail.elt.querySelector && event.detail.elt.querySelector('#editor')) {
  //   initializeEditor();
  // }
  // Apply syntax highlighting to any new code blocks
  // if (event.detail.elt.querySelector && event.detail.elt.querySelector('pre code')) {
  //   for (const elem of event.detail.elt.querySelectorAll('pre code')) {
  //     hljs.highlightElement(elem);
  //   }
  // }

  // Panel filter support
  if (event.detail.elt.querySelector && event.detail.elt.querySelector('.panel')) {
    initializePanelFilters(event.detail.elt.querySelectorAll('.panel'));
  }

  // Dropdown support
  if (event.detail.elt.querySelector && event.detail.elt.querySelector('.dropdown')) {
    // Initialize dropdown functionality
    const dropdowns = event.detail.elt.querySelectorAll('.dropdown');
    initializeDropdowns(dropdowns);
  }

  // File tree support
  if (event.detail.elt.querySelector && event.detail.elt.querySelector('.file-tree')) {
    // Add click handlers for files in the file tree
    document.querySelectorAll('.file-name').forEach(file => {
      file.addEventListener('click', function () {
        const path = this.getAttribute('data-path');
        const mime = this.getAttribute('data-mime');
        console.log(`File clicked: ${path} (${mime})`);
        // Here you can add code to handle file clicks, e.g., open file content
      });
    });
  }

  // Dropzone support
  if (event.detail.elt.querySelector && event.detail.elt.querySelector('#dropzone-container')) {
    initializeDropzone();
  }

  // Tags support
  if (event.detail.elt.querySelector && event.detail.elt.querySelector('.tag-entity-component')) {
    // Check if the swapped content contains our component
    const newComponents = event.detail.elt.querySelector('.tag-entity-component');
    newComponents.forEach(initializeTagAutocomplete);

    // Also check if the target *is* the component itself
    if (event.detail.target && event.detail.target.classList.contains('tag-entity-component')) {
      initializeTagAutocomplete(event.detail.target);
    }
  }
});

