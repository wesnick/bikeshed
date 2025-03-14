
import hljs from 'highlight.js';


// Function to apply syntax highlighting to code blocks
export function highlightCodeBlocks(codeBlocks = HTMLElement) {
  if (codeBlocks.length > 0) {
    console.log(`Highlighting ${codeBlocks.length} code blocks`);

    // Apply highlighting to each code block
    codeBlocks.forEach(block => {
      if (!block.classList.contains('hljs')) {
        hljs.highlightElement(block);
      }
    });
  }
}
