// Function to set up theme toggle
export function setupThemeToggle() {
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
export function updateThemeToggleAppearance(themeToggle) {
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
