// Import Bulma
import Bulma from '@vizuaalog/bulmajs';

// Import HTMX and extensions
import htmx from 'htmx.org';
import 'htmx-ext-sse';

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
});

export default {};
