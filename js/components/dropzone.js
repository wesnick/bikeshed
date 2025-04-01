import Dropzone from "dropzone";

let dropzone;

export function initializeDropzone() {
  dropzone = new Dropzone(document.getElementById('dropzone-container'), {
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
