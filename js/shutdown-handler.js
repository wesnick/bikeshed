import Bulma from "@vizuaalog/bulmajs";
import htmx from "htmx.org";


document.addEventListener('DOMContentLoaded', function() {
        // Check if we have a target path from redirect
        const urlParams = new URLSearchParams(window.location.search);
        const targetPath = urlParams.get('target_path');

        if (targetPath) {
            // Clean up the URL by removing the query parameter
            history.replaceState({}, '', targetPath);

            htmx.ajax('GET', targetPath, {
                  target: '.dashboard',   // The CSS selector for the target element
                  // swap: 'innerHTML',     // Optional: Specify the swap style (often defaults are fine)
                  pushUrl: true          // Equivalent to hx-push-url="true"
                  // source: document.body // Optional: Define the source element if needed for context/inheritance
                                           // Usually not required for this simple case.
              });

            document.body.dispatchEvent(new Event('route.updated'));
        }
    });


/**
 * Handles server shutdown events from SSE
 */
document.addEventListener('DOMContentLoaded', function() {

    document.body.addEventListener('htmx:sseClose', function (e) {
        const reason = e.detail.type
        switch (reason) {
            // case "nodeMissing":
            //     // Parent node is missing and therefore connection was closed
            // ...
            // case "nodeReplaced":
            //     // Parent node replacement caused closing of connection
            // ...
            case "message":
             // connection was closed due to reception of message sse-close
             console.log('Server shutdown detected:');


            // Use Bulma's native notification
            Bulma('#notification-area').notification({
                color: 'warning',
                body: "The server is restarting. The page has to reload cuz SSE does not reconnect. <button class=\"reload-page\">Reload</button>",

            }).show();

            setTimeout(() => {
                window.location.reload();
            }, 2000);
        }
    })

    document.body.addEventListener('htmx:afterSwap', function(event) {
        // Ensure we scroll the message container to the bottom after swap
        if (event.detail.elt.id === 'messages-container') {
         const messagesContainer = document.getElementById('dashboard-top');
            if (messagesContainer) {
                messagesContainer.scrollTo({
                    top: messagesContainer.scrollHeight - 200,
                    behavior: 'smooth'
                });
            }
        }
    });
    // Listen for the custom SSE event
    document.body.addEventListener('htmx:sseBeforeMessage', function(event) {
        console.log('[SSE Message] ', event.detail)

    });
});
