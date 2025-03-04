// Import Bulma
import Bulma from '@vizuaalog/bulmajs';

// Import components
import { initThemeToggle } from './components/theme.js';
import { initNavbar } from './components/navbar.js';
import { initChat } from './components/chat.js';

// Initialize components when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
  // Initialize theme toggle
  initThemeToggle();
  
  // Initialize navbar
  initNavbar();
  
  // Initialize chat
  initChat();
  
  // Initialize any Bulma components
  if (document.querySelector('#myModal')) {
    const modal = Bulma(document.querySelector('#myModal')).modal();
  }
});


