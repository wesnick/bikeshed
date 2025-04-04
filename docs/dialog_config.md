## Dialog Template Configuration

A Dialog is a non-branching exchange with an LLM that can produce an output.

These can be templated, using a key for template name

### Template Structure

| key             | type   | required | description                                                                                  |
|-----------------|--------|----------|----------------------------------------------------------------------------------------------|
| description     | string | false    | What does this do?                                                                           |
| model           | string | true     | default model to use (must be enabled)                                                       |
| tools           | list   | false    | list of tools to make available for each step, by default they will be included in LLM calls |
| resources       | list   | false    | list of resources to make available, this are available for templating                       |
| steps           | list   | true     | Ordered list of execution steps, each step is an object with a name and type                 |
| response_schema | list   | false    | If set, the finalize step will produce an artifact from the schema                           |


```yaml
dialog_templates:
  my_template:   # template name
    description: My great template
    model: ollama_chat/qwq:latest
    tools:
      - mcp:repomix
      - mcp:filesystem
    resources:
      - root:file://path/to/my/root
      - blob:uuid-of-blob
    steps: [] # List of steps to execute, documented below
    response_schema: my.schema  # optional, registered schema.  Finalize step will try to assemble this
```

### Step Structure

| key         | type    | description                                |
|-------------|---------|--------------------------------------------|
| name        | string  | Concise descriptive name                   |
| type        | string  | One of the defined step types              |
| enabled     | boolean | Whether the step is active (default: true) |

example:
```yaml
steps:
  - name: System prompt
    type: message
    role: system
    content: You are a nice bot.
```


### Step Types

- **message**: Saves a message to the dialog, does not send  
- **prompt**: Generate a completion from an LLM from a prompt
- **user_input**: Wait for user input.  Either triggers a completion, or continues based on an approval
- **invoke**: Run a tool.  This is a data manipulation step.
  - a native command
  - tool from MPC
  - logical tool (code as artifact, either python or javascript) 
    


```yaml
step_types:
  - message: # Print message with specified role
      fields:
        - role: string            # One of: "system", "user", "assistant"
        - content: string         # Text content of the message
        - template: string        # Registered template to use
        - template_defaults: dict # Arguments to pass to the template, default, overridden by context

  - prompt: # Generate completion from LLM
      fields:
        - content: string         # Direct content to use as prompt
        - template: string        # Registered template name to use
        - template_defaults: dict # Arguments to pass to the template, default, overridden by context
        - response_schema: string # Schema to validate LLM response
        - config: object          # Step-specific configuration overrides

  - user_input: # Wait for manual input from user
      fields:
        - prompt: string            # Text to display to user when requesting input
        - template: string          # Template to format user input, must have {{ user_input }} variable
        - response_schema: string   # Schema to validate LLM response
        - config: object            # Step-specific configuration

  - invoke: # Call code function
      fields:
        - callable: string          # Function identifier to call
        - response_schema: string   # Schema to validate function result

```

Common step params:
```yaml
  # Error handling for this step
  error_handling:
    strategy: string           # One of: "fail", "retry", "continue", "fallback"
    max_retries: integer       # Maximum retry attempts
    fallback_step: string      # Step ID to execute on failure

  # Configuration overrides for this step
  config:
    model: string                   # Override default model
    temperature: float              # Override default temperature
    max_tokens: integer             # Override default max tokens
    tools: list[string|object]      # Override or extend available tools
    resources: list[string|object]  # Override or extend available resources

```


