// Import HTMX and extensions
import htmx from 'htmx.org';
import 'htmx-ext-form-json';
import 'htmx-ext-sse';
import hljs from 'highlight.js';


import {initializeEditor} from './prosemirror';
import {initializePanelFilters} from './components/panel_filter';


import Dropzone from "dropzone";

// Import custom handlers
import './shutdown-handler';
import './components/tags';


// Function to close the modal
function closeModal() {
  const modal = document.getElementById('modal-container');
  if (modal) {
    modal.classList.remove('is-active');
    // Clear content to prevent brief flash of old content
    const modalContent = modal.querySelector('.modal-content');
    if (modalContent) {
      modalContent.innerHTML = '';
    }
  }
  document.documentElement.classList.remove('is-clipped'); // Remove clipping from HTML tag
}

// Initialize application
document.addEventListener('DOMContentLoaded', () => {
  console.log('BikeShed application initialized');

  // Ensure SSE extension is properly initialized
  if (typeof htmx !== 'undefined') {
    console.log('HTMX loaded successfully');

    // Log SSE connection events
    document.body.addEventListener('htmx:sseOpen', function (event) {
      console.log('SSE Connected');
    });

    // Listen for history changes and dispatch route.changed event
    document.body.addEventListener('htmx:pushedIntoHistory', function (event) {
      console.log('Route changed:', window.location.pathname);
      document.body.dispatchEvent(new Event('route.updated'));
    });

  } else {
    console.error('HTMX not loaded properly');
  }

  // Initialize theme from localStorage
  initializeTheme();
  setupThemeToggle();

  // Add event listeners for closing the modal
  const modalContainer = document.getElementById('modal-container');
  if (modalContainer) {
    const modalBackground = modalContainer.querySelector('.modal-background');
    const modalCloseButton = modalContainer.querySelector('.modal-close');

    if (modalBackground) {
      modalBackground.addEventListener('click', closeModal);
    }
    if (modalCloseButton) {
      modalCloseButton.addEventListener('click', closeModal);
    }
  }

  // Add listener for SSE-triggered close
  document.body.addEventListener('modal.close', closeModal);

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

  // Check if the swap target is the modal content area
  const modalContent = document.getElementById('modal-container')?.querySelector('.modal-content');
  if (modalContent && event.detail.target === modalContent) {
    const modal = document.getElementById('modal-container');
    if (modal) {
      modal.classList.add('is-active');
      document.documentElement.classList.add('is-clipped'); // Add clipping to HTML tag

      // Re-initialize dropdowns etc. if they exist within the modal
      if (modal.querySelector('.dropdown')) {
        initializeDropdowns(modal.querySelectorAll('.dropdown'));
      }
      // Add other component initializations needed within modals here
    }
  }

  // if (event.detail.elt.querySelector && event.detail.elt.querySelector('#editor')) {
  //   initializeEditor();
  // }
  // Apply syntax highlighting to any new code blocks
  // if (event.detail.elt.querySelector && event.detail.elt.querySelector('pre code')) {
  //   for (const elem of event.detail.elt.querySelectorAll('pre code')) {
  //     hljs.highlightElement(elem);
  //   }
  // }

  if (event.detail.elt.querySelector && event.detail.elt.querySelector('.panel')) {
    initializePanelFilters(event.detail.elt.querySelectorAll('.panel'));
  }

  // Activate bulma JS behaviors on newly added elements
  if (event.detail.elt.querySelector && event.detail.elt.querySelector('.dropdown')) {
    // Initialize dropdown functionality
    const dropdowns = event.detail.elt.querySelectorAll('.dropdown');
    initializeDropdowns(dropdowns);
  }

  // File tree support
  if (event.detail.elt.querySelector && event.detail.elt.querySelector('.file-tree')) {
    // Add click handlers for files in the file tree
    document.querySelectorAll('.file-name').forEach(file => {
      file.addEventListener('click', function() {
        const path = this.getAttribute('data-path');
        const mime = this.getAttribute('data-mime');
        console.log(`File clicked: ${path} (${mime})`);
        // Here you can add code to handle file clicks, e.g., open file content
      });
    });
  }

  // Dropzone support
  if (event.detail.elt.querySelector && event.detail.elt.querySelector('#dropzone-container')) {
    const dropzone = new Dropzone(document.getElementById('dropzone-container'), {
      url: "/blobs/upload-multi",
      paramName: function () {
        return 'files'
      },
      maxFilesize: 30, // MB
      // acceptedFiles: ".jpg,.jpeg,.png,.gif,.pdf,.doc,.docx,.xls,.xlsx,.txt,.zip",
      uploadMultiple: true,
      parallelUploads: 5,
      dictDefaultMessage: "Drop files here or click to upload (max 30MB per file)",
      success: function (file, response) {
        // Refresh the file list using HTMX after upload
        //htmx.trigger("#file-list", "htmx:load");
      },
      error: function (file, errorMessage) {
        console.error("Upload error:", errorMessage);
        file.previewElement.classList.add("dz-error");

        // Add error message to the file preview
        const errorElement = file.previewElement.querySelector("[data-dz-errormessage]");
        errorElement.textContent = typeof errorMessage === "string" ?
          errorMessage :
          errorMessage.error || "Upload failed";
      }
    });
    console.log('dropzone initialized');
    dropzone.on('addedfile', file => {
      console.log(`File added: ${file.name}`);
    })
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
  newThemeToggle.addEventListener('click', function (e) {
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

// Function to initialize dropdown functionality
function initializeDropdowns(dropdowns) {
  dropdowns.forEach(dropdown => {
    // Remove any existing event listeners by cloning and replacing the trigger button
    const trigger = dropdown.querySelector('.dropdown-trigger button');
    if (!trigger) return;
    
    const newTrigger = trigger.cloneNode(true);
    trigger.parentNode.replaceChild(newTrigger, trigger);
    
    // Add click event listener to toggle dropdown
    newTrigger.addEventListener('click', function(e) {
      e.preventDefault();
      e.stopPropagation();
      
      // Close all other dropdowns
      document.querySelectorAll('.dropdown.is-active').forEach(activeDropdown => {
        if (activeDropdown !== dropdown) {
          activeDropdown.classList.remove('is-active');
        }
      });
      
      // Toggle current dropdown
      dropdown.classList.toggle('is-active');
    });
  });
  
  // Close dropdowns when clicking outside
  document.addEventListener('click', function(e) {
    if (!e.target.closest('.dropdown')) {
      document.querySelectorAll('.dropdown.is-active').forEach(dropdown => {
        dropdown.classList.remove('is-active');
      });
    }
  });
}

// Initialize dropdowns on page load
document.addEventListener('DOMContentLoaded', function() {
  const dropdowns = document.querySelectorAll('.dropdown');
  if (dropdowns.length > 0) {
    initializeDropdowns(dropdowns);
  }
});

