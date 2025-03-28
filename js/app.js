// Import HTMX and extensions
import htmx from 'htmx.org';
import 'htmx-ext-form-json';
import 'htmx-ext-sse';
import hljs from 'highlight.js';
// import Bulma from "@vizuaalog/bulmajs";
import Dropdown from "@vizuaalog/bulmajs/src/plugins/dropdown";

import {initializeEditor} from './prosemirror';

import Dropzone from "dropzone";

import BulmaTagsInput from "@creativebulma/bulma-tagsinput";
// Import custom handlers
import './shutdown-handler';


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

  // Tags input
  if (event.detail.elt.querySelector && event.detail.elt.querySelector('.tags-input')) {

    const tagsInput = event.detail.elt.querySelector('.tags-input');

    new BulmaTagsInput(tagsInput, {
      source: async function (value) {
        // Value equal input value
        // We can then use it to request data from external API
        return await fetch("/tags/autocomplete/" + value)
          .then(function (response) {
            return response.json();
          });
      },

    });

    tagsInput.BulmaTagsInput().on('after.add', function (data) {
      console.log(data, 'after.add');
      // Set the tag ID and action in the form
      const tagId = data.item.value;
      document.getElementById('tag-id').value = tagId;
      document.getElementById('tag-action').value = 'add';
      
      // Trigger custom event to submit the form
      document.body.dispatchEvent(new CustomEvent('tagAdded'));
    })
    
    tagsInput.BulmaTagsInput().on('after.remove', function (data) {
      console.log(data, 'after.remove');
      // Set the tag ID and action in the form
      const tagId = data.item.value;
      document.getElementById('tag-id').value = tagId;
      document.getElementById('tag-action').value = 'remove';
      
      // Trigger custom event to submit the form
      document.body.dispatchEvent(new CustomEvent('tagRemoved'));
    })

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

  // Activate bulma JS behaviors on newly added elements
  if (event.detail.elt.querySelector && event.detail.elt.querySelector('.dropdown')) {
    Dropdown.parseDocument();
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

