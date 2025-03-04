/**
 * Theme toggle functionality
 */
export function initThemeToggle() {
  // Initialize theme from localStorage
  const savedTheme = localStorage.getItem('theme');
  if (savedTheme) {
    document.documentElement.setAttribute('data-theme', savedTheme);
    
    // Update toggle button to match current theme
    updateThemeUI(savedTheme);
  }
  
  // Add event listener to theme toggle button
  const themeToggle = document.querySelector('.theme-toggle');
  if (themeToggle) {
    themeToggle.addEventListener('click', toggleTheme);
  }
}

export function toggleTheme() {
  const html = document.documentElement;
  const currentTheme = html.getAttribute('data-theme');
  const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
  
  html.setAttribute('data-theme', newTheme);
  
  // Update toggle button text and icon
  updateThemeUI(newTheme);
  
  // Save preference to localStorage
  localStorage.setItem('theme', newTheme);
}

function updateThemeUI(theme) {
  const themeIcon = document.querySelector('.theme-toggle .icon i');
  const themeText = document.querySelector('.theme-toggle .theme-text');
  
  if (theme === 'dark') {
    themeIcon.className = 'fas fa-sun';
    themeText.textContent = 'Light Mode';
  } else {
    themeIcon.className = 'fas fa-moon';
    themeText.textContent = 'Dark Mode';
  }
}
