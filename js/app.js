// Import Bulma
import Bulma from '@vizuaalog/bulmajs';

// Import components
import { initThemeToggle } from './components/theme.js';
import { initNavbar, toggleSidebar } from './components/navbar.js';
import { initChat, startTimer, stopTimer } from './components/chat.js';

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

// Make functions available globally
window.toggleSidebar = toggleSidebar;
window.startTimer = startTimer;
window.stopTimer = stopTimer;
