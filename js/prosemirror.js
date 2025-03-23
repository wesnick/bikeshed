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

]


export function initializeEditor() {
    // Create and mount the editor
  const editorElement = document.getElementById('editor');
  const button = document.getElementById('editor-button');

  let view = new MarkdownView(editorElement, editorElement.innerHTML);

  button.addEventListener("change", () => {
    let View = button.checked ? MarkdownView : ProseMirrorView
    if (view instanceof View) return
    let content = view.content
    view.destroy()
    view = new View(editorElement, content)
    view.focus()
  })
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

