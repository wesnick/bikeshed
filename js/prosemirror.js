import {EditorState} from "prosemirror-state";
import {EditorView} from "prosemirror-view";
import {Schema, DOMSerializer} from "prosemirror-model";
import {
  schema,
  defaultMarkdownParser,
  defaultMarkdownSerializer
} from "prosemirror-markdown";
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
import {exampleSetup, buildInputRules, buildKeymap, buildMenuItems} from "prosemirror-example-setup";
import {dropCursor} from "prosemirror-dropcursor";
import {gapCursor} from "prosemirror-gapcursor";
import {menuBar} from "prosemirror-menu";
// import hljs from 'highlight.js';

const bsSchema = schema;

const plugins = [
      buildInputRules(bsSchema),
      keymap(buildKeymap(bsSchema)),
      keymap(baseKeymap),
      dropCursor(),
      gapCursor(),

      history(),
      menuBar({
        floating: false,
        content: buildMenuItems(bsSchema).fullMenu
      }),
      // keymap({
      //   'Mod-z': undo,
      //   'Mod-y': redo,
      //   'Shift-Mod-z': redo,
      //   'Enter': chainCommands(
      //     newlineInCode,
      //     createParagraphNear,
      //     liftEmptyBlock,
      //     splitBlock
      //   )
      // }),

]


export function initializeEditor() {
    // Create and mount the editor
  const editorElement = document.getElementById('editor');

  // Add a button after the editorElement
  const buttonContainer = document.createElement('div');
  const button = document.createElement('input');
  button.type = "checkbox"
  button.value = "markdown"
  button.id = "markdown-checkbox"
  button.checked = true
  const label = document.createElement('label');
  label.htmlFor = "markdown-checkbox"
  label.textContent = "Markdown"
  buttonContainer.appendChild(button);
  buttonContainer.appendChild(label);
  editorElement.parentNode.insertBefore(buttonContainer, editorElement.nextSibling);


  let view = new MarkdownView(editorElement, editorElement.innerHTML)

  button.addEventListener("change", () => {

    let View = button.checked ? MarkdownView : ProseMirrorView
    if (view instanceof View) return
    let content = view.content
    view.destroy()
    view = new View(editorElement, content)
    view.focus()
  })


  // const bsSchema = new Schema({
  //   nodes: {
  //     // Basic nodes
  //     doc: {
  //       content: "block+"
  //     },
  //     paragraph: {
  //       content: "inline*",
  //       group: "block",
  //       parseDOM: [{tag: "p"}],
  //       toDOM() {
  //         return ["p", 0]
  //       }
  //     },
  //     blockquote: {
  //       content: "block+",
  //       group: "block",
  //       parseDOM: [{tag: "blockquote"}],
  //       toDOM() {
  //         return ["blockquote", 0]
  //       }
  //     },
  //     horizontal_rule: {
  //       group: "block",
  //       parseDOM: [{tag: "hr"}],
  //       toDOM() {
  //         return ["hr"]
  //       }
  //     },
  //     heading: {
  //       attrs: {level: {default: 1}},
  //       content: "inline*",
  //       group: "block",
  //       defining: true,
  //       parseDOM: [
  //         {tag: "h1", attrs: {level: 1}},
  //         {tag: "h2", attrs: {level: 2}},
  //         {tag: "h3", attrs: {level: 3}},
  //         {tag: "h4", attrs: {level: 4}},
  //         {tag: "h5", attrs: {level: 5}},
  //         {tag: "h6", attrs: {level: 6}}
  //       ],
  //       toDOM(node) {
  //         return ["h" + node.attrs.level, 0]
  //       }
  //     },
  //     code_block: {
  //       attrs: {language: {default: ""}},
  //       content: "text*",
  //       group: "block",
  //       code: true,
  //       defining: true,
  //       marks: "",
  //       parseDOM: [{
  //         tag: "pre",
  //         preserveWhitespace: "full",
  //         getAttrs: node => ({language: node.getAttribute("data-language") || ""})
  //       }],
  //       toDOM(node) {
  //         return [
  //           "div", {class: "code-block"},
  //           ["div", {class: "code-language"}, node.attrs.language],
  //           ["pre", {"data-language": node.attrs.language}, ["code", {class: `language-${node.attrs.language}`}, 0]]
  //         ]
  //       }
  //     },
  //     text: {
  //       group: "inline"
  //     },
  //     image: {
  //       inline: true,
  //       attrs: {
  //         src: {},
  //         alt: {default: null},
  //         title: {default: null}
  //       },
  //       group: "inline",
  //       draggable: true,
  //       parseDOM: [{
  //         tag: "img[src]",
  //         getAttrs(dom) {
  //           return {
  //             src: dom.getAttribute("src"),
  //             alt: dom.getAttribute("alt"),
  //             title: dom.getAttribute("title")
  //           }
  //         }
  //       }],
  //       toDOM(node) {
  //         return ["img", node.attrs]
  //       }
  //     },
  //     hard_break: {
  //       inline: true,
  //       group: "inline",
  //       selectable: false,
  //       parseDOM: [{tag: "br"}],
  //       toDOM() {
  //         return ["br"]
  //       }
  //     }
  //   },
  //   marks: {
  //     em: {
  //       parseDOM: [{tag: "i"}, {tag: "em"}, {style: "font-style=italic"}],
  //       toDOM() {
  //         return ["em"]
  //       }
  //     },
  //     strong: {
  //       parseDOM: [{tag: "strong"}, {tag: "b"}, {style: "font-weight=bold"}],
  //       toDOM() {
  //         return ["strong"]
  //       }
  //     },
  //     code: {
  //       parseDOM: [{tag: "code"}],
  //       toDOM() {
  //         return ["code"]
  //       }
  //     },
  //     link: {
  //       attrs: {
  //         href: {},
  //         title: {default: null}
  //       },
  //       inclusive: false,
  //       parseDOM: [{
  //         tag: "a[href]",
  //         getAttrs(dom) {
  //           return {href: dom.getAttribute("href"), title: dom.getAttribute("title")}
  //         }
  //       }],
  //       toDOM(node) {
  //         return ["a", node.attrs, 0]
  //       }
  //     }
  //   }
  // });


  // Set up the editor state

  // // Create the editor view
  // const view = new EditorView(editorElement, {
  //   state,
  //   dispatchTransaction(transaction) {
  //     const newState = view.state.apply(transaction);
  //     view.updateState(newState);
  //
  //   }
  // });

  // // Initialize plugins
  // const slashPlugin = new SlashCommandPlugin(view);
  // const codeBlockPlugin = new CodeBlockPlugin(view);

  // // Add event listener for key down
  // view.dom.addEventListener('keydown', (event) => {
  //   if (codeBlockPlugin.handleKeyDown(view, event)) {
  //     event.preventDefault();
  //   }
  // });

  // // Function to update the preview
  // function updatePreview() {
  //   // Convert the document to Markdown
  //   const markdown = defaultMarkdownSerializer.serialize(view.state.doc);
  //
  //   // Convert markdown to HTML and update the preview
  //   previewElement.innerHTML = markdown;
  //
  //   // Update plugins
  //   slashPlugin.update(view, view.state);
  //   codeBlockPlugin.update(view, view.state);
  //
  //   // For debugging
  //   console.log("Generated Markdown:", markdown);
  // }


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
  // updatePreview();
}


class ProseMirrorView {
  constructor(target, content) {
    this.view = new EditorView(target, {
      state: EditorState.create({
        doc: defaultMarkdownParser.parse(content),
        schema: bsSchema,
        plugins,
      })
    })
  }

  get content() {
    return defaultMarkdownSerializer.serialize(this.view.state.doc)
  }
  focus() { this.view.focus() }
  destroy() { this.view.destroy() }
}


class MarkdownView {
  constructor(target, content) {
    this.textarea = target.appendChild(document.createElement("textarea"))
    this.textarea.value = content;
  }

  get content() {
    return this.textarea.value
  }

  focus() {
    this.textarea.focus()
  }
  destroy() {
    this.textarea.remove()
  }
}

