// Import ProseMirror modules
import {EditorState} from "prosemirror-state";
import {EditorView} from "prosemirror-view";
import {Schema} from "prosemirror-model";
import {keymap} from "prosemirror-keymap";
import {
  baseKeymap,
  chainCommands,
  createParagraphNear,
  liftEmptyBlock,
  newlineInCode,
  splitBlock
} from "prosemirror-commands";
import {history, redo, undo} from "prosemirror-history";
import {highlightCodeBlocks} from './code_highlight';

export function initializeEditor() {
    // Create and mount the editor
  const editorElement = document.getElementById('editor');
  const previewElement = document.getElementById('preview');

  console.log('trying to load prosemirror');
  // Define a custom schema extending the basic schema
  const bsSchema = new Schema({
    nodes: {
      // Basic nodes
      doc: {
        content: "block+"
      },
      paragraph: {
        content: "inline*",
        group: "block",
        parseDOM: [{tag: "p"}],
        toDOM() {
          return ["p", 0]
        }
      },
      blockquote: {
        content: "block+",
        group: "block",
        parseDOM: [{tag: "blockquote"}],
        toDOM() {
          return ["blockquote", 0]
        }
      },
      horizontal_rule: {
        group: "block",
        parseDOM: [{tag: "hr"}],
        toDOM() {
          return ["hr"]
        }
      },
      heading: {
        attrs: {level: {default: 1}},
        content: "inline*",
        group: "block",
        defining: true,
        parseDOM: [
          {tag: "h1", attrs: {level: 1}},
          {tag: "h2", attrs: {level: 2}},
          {tag: "h3", attrs: {level: 3}},
          {tag: "h4", attrs: {level: 4}},
          {tag: "h5", attrs: {level: 5}},
          {tag: "h6", attrs: {level: 6}}
        ],
        toDOM(node) {
          return ["h" + node.attrs.level, 0]
        }
      },
      code_block: {
        attrs: {language: {default: ""}},
        content: "text*",
        group: "block",
        code: true,
        defining: true,
        marks: "",
        parseDOM: [{
          tag: "pre",
          preserveWhitespace: "full",
          getAttrs: node => ({language: node.getAttribute("data-language") || ""})
        }],
        toDOM(node) {
          return [
            "div", {class: "code-block"},
            ["div", {class: "code-language"}, node.attrs.language],
            ["pre", {"data-language": node.attrs.language}, ["code", {class: `language-${node.attrs.language}`}, 0]]
          ]
        }
      },
      text: {
        group: "inline"
      },
      image: {
        inline: true,
        attrs: {
          src: {},
          alt: {default: null},
          title: {default: null}
        },
        group: "inline",
        draggable: true,
        parseDOM: [{
          tag: "img[src]",
          getAttrs(dom) {
            return {
              src: dom.getAttribute("src"),
              alt: dom.getAttribute("alt"),
              title: dom.getAttribute("title")
            }
          }
        }],
        toDOM(node) {
          return ["img", node.attrs]
        }
      },
      hard_break: {
        inline: true,
        group: "inline",
        selectable: false,
        parseDOM: [{tag: "br"}],
        toDOM() {
          return ["br"]
        }
      }
    },
    marks: {
      em: {
        parseDOM: [{tag: "i"}, {tag: "em"}, {style: "font-style=italic"}],
        toDOM() {
          return ["em"]
        }
      },
      strong: {
        parseDOM: [{tag: "strong"}, {tag: "b"}, {style: "font-weight=bold"}],
        toDOM() {
          return ["strong"]
        }
      },
      code: {
        parseDOM: [{tag: "code"}],
        toDOM() {
          return ["code"]
        }
      },
      link: {
        attrs: {
          href: {},
          title: {default: null}
        },
        inclusive: false,
        parseDOM: [{
          tag: "a[href]",
          getAttrs(dom) {
            return {href: dom.getAttribute("href"), title: dom.getAttribute("title")}
          }
        }],
        toDOM(node) {
          return ["a", node.attrs, 0]
        }
      }
    }
  });

  // Plugin to handle slash commands
  class SlashCommandPlugin {
    constructor(view) {
      this.view = view;
      this.slashMenuOpen = false;
      this.slashMenuEl = null;
      this.slashMenuPosition = null;
      this.slashMenuItems = [
        {
          id: 'heading1',
          title: 'Heading 1',
          icon: 'heading',
          execute: () => this.insertHeading(1)
        },
        {
          id: 'heading2',
          title: 'Heading 2',
          icon: 'heading',
          execute: () => this.insertHeading(2)
        },
        {
          id: 'heading3',
          title: 'Heading 3',
          icon: 'heading',
          execute: () => this.insertHeading(3)
        },
        {
          id: 'bullet-list',
          title: 'Bullet List',
          icon: 'list-ul',
          execute: () => this.insertBulletList()
        },
        {
          id: 'numbered-list',
          title: 'Numbered List',
          icon: 'list-ol',
          execute: () => this.insertNumberedList()
        },
        {
          id: 'blockquote',
          title: 'Blockquote',
          icon: 'quote-left',
          execute: () => this.insertBlockquote()
        },
        {
          id: 'code-block',
          title: 'Code Block',
          icon: 'code',
          execute: () => this.insertCodeBlock()
        },
        {
          id: 'hr',
          title: 'Horizontal Rule',
          icon: 'minus',
          execute: () => this.insertHorizontalRule()
        },
        {
          id: 'img',
          title: 'Image',
          icon: 'image',
          execute: () => this.insertImage()
        }
      ];

      this.createSlashMenu();
    }

    createSlashMenu() {
      const menu = document.createElement('div');
      menu.className = 'slash-menu';
      menu.style.display = 'none';

      const searchBox = document.createElement('div');
      searchBox.className = 'slash-menu-search';
      searchBox.innerHTML = `<input type="text" placeholder="Filter commands...">`;
      menu.appendChild(searchBox);

      const menuItems = document.createElement('div');
      menuItems.className = 'slash-menu-items';

      this.slashMenuItems.forEach(item => {
        const menuItem = document.createElement('div');
        menuItem.className = 'slash-menu-item';
        menuItem.dataset.id = item.id;
        menuItem.innerHTML = `
              <span class="slash-menu-item-icon">
                <i class="fas fa-${item.icon}"></i>
              </span>
              <span>${item.title}</span>
            `;
        menuItem.addEventListener('click', () => {
          this.executeSlashCommand(item.id);
          this.closeSlashMenu();
        });
        menuItems.appendChild(menuItem);
      });

      menu.appendChild(menuItems);
      document.body.appendChild(menu);

      const searchInput = searchBox.querySelector('input');
      searchInput.addEventListener('input', () => {
        const value = searchInput.value.toLowerCase();

        const items = menuItems.querySelectorAll('.slash-menu-item');
        items.forEach(item => {
          const text = item.textContent.toLowerCase();
          item.style.display = text.includes(value) ? 'flex' : 'none';
        });
      });

      this.slashMenuEl = menu;

      // Close the menu when clicking outside
      document.addEventListener('click', event => {
        if (this.slashMenuOpen && !menu.contains(event.target)) {
          this.closeSlashMenu();
        }
      });
    }

    openSlashMenu(pos) {
      const editorRect = this.view.dom.getBoundingClientRect();
      const coords = this.view.coordsAtPos(pos);

      this.slashMenuEl.style.left = `${coords.left - editorRect.left}px`;
      this.slashMenuEl.style.top = `${coords.bottom - editorRect.top + 5}px`;
      this.slashMenuEl.style.display = 'block';

      const searchInput = this.slashMenuEl.querySelector('input');
      searchInput.value = '';
      searchInput.focus();

      // Show all items
      const items = this.slashMenuEl.querySelectorAll('.slash-menu-item');
      items.forEach(item => {
        item.style.display = 'flex';
      });

      this.slashMenuOpen = true;
      this.slashMenuPosition = pos;
    }

    closeSlashMenu() {
      this.slashMenuEl.style.display = 'none';
      this.slashMenuOpen = false;
      this.slashMenuPosition = null;
    }

    executeSlashCommand(commandId) {
      const command = this.slashMenuItems.find(item => item.id === commandId);
      if (command) {
        command.execute();
      }
    }

    update(view, prevState) {
      this.view = view;

      const state = view.state;
      const selection = state.selection;

      // Find the slash command
      if (selection.empty) {
        const $pos = selection.$from;
        const textBefore = $pos.parent.textContent.slice(0, $pos.parentOffset);

        if (textBefore.endsWith('/')) {
          // Open slash menu
          this.openSlashMenu($pos.pos);
        } else if (this.slashMenuOpen && !textBefore.includes('/')) {
          // Close slash menu if there's no slash
          this.closeSlashMenu();
        }
      }
    }

    insertHeading(level) {
      const {state, dispatch} = this.view;

      // Delete the slash character
      const {$from} = state.selection;
      const transaction = state.tr.delete($from.pos - 1, $from.pos);

      // Insert heading node
      const nodeType = bsSchema.nodes.heading;
      dispatch(transaction.replaceSelectionWith(nodeType.create({level})));

      this.view.focus();
    }

    insertBlockquote() {
      const {state, dispatch} = this.view;

      // Delete the slash character
      const {$from} = state.selection;
      const transaction = state.tr.delete($from.pos - 1, $from.pos);

      // Insert blockquote node
      const nodeType = bsSchema.nodes.blockquote;
      const paragraph = bsSchema.nodes.paragraph.create();
      dispatch(transaction.replaceSelectionWith(nodeType.create({}, paragraph)));

      this.view.focus();
    }

    insertCodeBlock() {
      const {state, dispatch} = this.view;

      // Delete the slash character
      const {$from} = state.selection;
      const transaction = state.tr.delete($from.pos - 1, $from.pos);

      // Insert code block node
      const nodeType = bsSchema.nodes.code_block;
      dispatch(transaction.replaceSelectionWith(nodeType.create({language: 'javascript'})));

      this.view.focus();
    }

    insertHorizontalRule() {
      const {state, dispatch} = this.view;

      // Delete the slash character
      const {$from} = state.selection;
      const transaction = state.tr.delete($from.pos - 1, $from.pos);

      // Insert horizontal rule node
      const nodeType = bsSchema.nodes.horizontal_rule;
      dispatch(transaction.replaceSelectionWith(nodeType.create()));

      this.view.focus();
    }

    insertBulletList() {
      const {state, dispatch} = this.view;

      // Delete the slash character
      const {$from} = state.selection;
      const transaction = state.tr.delete($from.pos - 1, $from.pos);

      // We'd need to create a proper list plugin for this to work
      // For now, let's just create a paragraph with a bullet character
      const nodeType = bsSchema.nodes.paragraph;
      dispatch(transaction.replaceSelectionWith(nodeType.create(
        null,
        bsSchema.text('• ')
      )));

      this.view.focus();
    }

    insertNumberedList() {
      const {state, dispatch} = this.view;

      // Delete the slash character
      const {$from} = state.selection;
      const transaction = state.tr.delete($from.pos - 1, $from.pos);

      // We'd need to create a proper list plugin for this to work
      // For now, let's just create a paragraph with a number
      const nodeType = bsSchema.nodes.paragraph;
      dispatch(transaction.replaceSelectionWith(nodeType.create(
        null,
        bsSchema.text('1. ')
      )));

      this.view.focus();
    }

    insertImage() {
      const {state, dispatch} = this.view;

      // Delete the slash character
      const {$from} = state.selection;
      const transaction = state.tr.delete($from.pos - 1, $from.pos);

      // Prompt for image URL
      const url = prompt('Enter image URL:');
      if (url) {
        // Insert image node
        const nodeType = bsSchema.nodes.image;
        dispatch(transaction.replaceSelectionWith(nodeType.create({src: url, alt: 'Image'})));
      } else {
        // Just delete the slash
        dispatch(transaction);
      }

      this.view.focus();
    }
  }

  // Plugin to handle code blocks and syntax highlighting
  class CodeBlockPlugin {
    constructor(view) {
      this.view = view;
      this.updating = false;
    }

    update(view, prevState) {
      this.view = view;

      if (this.updating) return;
      this.updating = true;

      // Find all code blocks and apply syntax highlighting
      const nodes = document.querySelectorAll('.ProseMirror pre code');
      nodes.forEach(node => {
        const parent = node.closest('.code-block');
        if (parent) {
          const language = parent.querySelector('.code-language').textContent;
          if (language && !node.classList.contains(`language-${language}`)) {
            node.className = `language-${language}`;
            highlightCodeBlocks(node);
          }
        }
      });

      this.updating = false;
    }

    // Check if we need to insert a code block
    handleKeyDown(view, event) {
      if (event.key === '`' && this.checkForTripleBacktick(view)) {
        const {state, dispatch} = view;
        const {$from} = state.selection;

        // Delete the triple backtick
        let transaction = state.tr.delete($from.pos - 3, $from.pos);

        // Insert code block
        const nodeType = bsSchema.nodes.code_block;
        dispatch(transaction.replaceSelectionWith(nodeType.create({language: 'javascript'})));

        return true;
      }
      return false;
    }

    checkForTripleBacktick(view) {
      const {state} = view;
      const {$from} = state.selection;
      const textBefore = $from.parent.textContent.slice(0, $from.parentOffset);

      return textBefore.endsWith('``');
    }
  }


  // Set up the editor state
  const state = EditorState.create({
    schema: bsSchema,
    plugins: [
      history(),
      keymap({
        'Mod-z': undo,
        'Mod-y': redo,
        'Shift-Mod-z': redo,
        'Enter': chainCommands(
          newlineInCode,
          createParagraphNear,
          liftEmptyBlock,
          splitBlock
        )
      }),
      keymap(baseKeymap)
    ]
  });

  // Create the editor view
  const view = new EditorView(editorElement, {
    state,
    dispatchTransaction(transaction) {
      const newState = view.state.apply(transaction);
      view.updateState(newState);

      // Update the preview
      updatePreview();
    }
  });

  // Initialize plugins
  const slashPlugin = new SlashCommandPlugin(view);
  const codeBlockPlugin = new CodeBlockPlugin(view);

  // Add event listener for key down
  view.dom.addEventListener('keydown', (event) => {
    if (codeBlockPlugin.handleKeyDown(view, event)) {
      event.preventDefault();
    }
  });

  // Function to update the preview
  function updatePreview() {
    console.log(previewElement);
    previewElement.innerHTML = view.dom.innerHTML;

    // Update plugins
    slashPlugin.update(view, view.state);
    codeBlockPlugin.update(view, view.state);

    // Apply syntax highlighting to the preview
    const codeBlocks = previewElement.querySelectorAll('pre code');
    codeBlocks.forEach(block => {
      console.log('code highlight now');
    });
  }


  // document.getElementById('reset-button').addEventListener('click', () => {
  //   // Create a new state with empty content
  //   const newState = EditorState.create({
  //     schema: bsSchema,
  //     plugins: [
  //       history(),
  //       keymap({
  //         'Mod-z': undo,
  //         'Mod-y': redo,
  //         'Shift-Mod-z': redo,
  //         'Enter': chainCommands(
  //           newlineInCode,
  //           createParagraphNear,
  //           liftEmptyBlock,
  //           splitBlock
  //         )
  //       }),
  //       keymap(baseKeymap)
  //     ]
  //   });
  //
  //   view.updateState(newState);
  //   updatePreview();
  // });

  // Initialize the preview
  updatePreview();
}
