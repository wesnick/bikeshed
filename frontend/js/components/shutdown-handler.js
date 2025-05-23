import htmx from "htmx.org";

export function handleSPARefresh() {
  // Check if we have a target path from redirect
  const urlParams = new URLSearchParams(window.location.search);
  const targetPath = urlParams.get('target_path');

  console.log(targetPath);
  if (targetPath) {
    // Clean up the URL by removing the query parameter
    history.replaceState({}, '', targetPath);

    htmx.ajax('GET', targetPath, {
      target: '.dashboard',
      pushUrl: true
    });

    document.body.dispatchEvent(new Event('route.updated'));
  }
}

export function shutdownHandler(event) {
  const reason = event.detail.type
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

      // Updated to use Bootstrap alert classes
      const html_template = `<div class="alert alert-primary" role="alert">
  The server is restarting. The page has to reload because SSE does not automatically reconnect.
</div>`;

      const notificationArea = document.getElementById('notification-area');
      if (notificationArea) {
        notificationArea.innerHTML = html_template;
      }

      setTimeout(() => {
        window.location.reload();
      }, 2000);
  }
}
