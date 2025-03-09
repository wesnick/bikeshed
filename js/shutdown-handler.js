/**
 * Handles server shutdown events from SSE
 */
document.addEventListener('DOMContentLoaded', function() {
    // Listen for the custom SSE event
    document.body.addEventListener('htmx:sseMessage', function(event) {
        // Check if this is a server_shutdown event
        if (event.detail.event === 'server_shutdown') {
            console.log('Server shutdown detected');
            
            // Show a notification to the user
            const notification = document.createElement('div');
            notification.className = 'notification is-warning is-light';
            notification.style.position = 'fixed';
            notification.style.top = '1rem';
            notification.style.right = '1rem';
            notification.style.zIndex = '9999';
            notification.innerHTML = `
                <button class="delete"></button>
                <strong>Server Shutting Down</strong>
                <p>The server is restarting. This page will automatically reconnect when the server is back online.</p>
            `;
            
            document.body.appendChild(notification);
            
            // Add event listener to the delete button
            notification.querySelector('.delete').addEventListener('click', function() {
                notification.remove();
            });
            
            // Automatically remove the notification after 10 seconds
            setTimeout(() => {
                if (notification.parentNode) {
                    notification.remove();
                }
            }, 10000);
        }
    });
});
