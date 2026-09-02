# Install Negroni Governed Agents

The canonical package is `skills/negroni-governed-agents`. It follows the portable `SKILL.md` layout and has no runtime dependencies.

## Claude Code

### Plugin installation from this repository

Inside Claude Code:

```text
/plugin marketplace add sam999-code/Negroni-Project
/plugin install negroni-project@negroni-project
```

Invoke it with:

```text
/negroni-project:negroni-governed-agents
```

For local development without installation:

```text
claude --plugin-dir ./Negroni-Project
```

### Manual personal installation

Copy `skills/negroni-governed-agents` to `~/.claude/skills/negroni-governed-agents`. Invoke it as `/negroni-governed-agents`.

## Hermes Agent

Install directly from the public GitHub skill path:

```text
hermes skills install sam999-code/Negroni-Project/skills/negroni-governed-agents
```

Or add the repository as a reusable skill source:

```text
hermes skills tap add sam999-code/Negroni-Project
hermes skills install sam999-code/Negroni-Project/negroni-governed-agents
```

Invoke it in Hermes with `/negroni-governed-agents` or ask Hermes to load the skill by name.

## OpenAI Codex

Copy `skills/negroni-governed-agents` to the user skills directory:

- macOS/Linux: `~/.codex/skills/negroni-governed-agents`
- Windows: `%USERPROFILE%\.codex\skills\negroni-governed-agents`

Restart Codex if needed, then invoke `$negroni-governed-agents`.

## Other LLMs

For ChatGPT, Gemini, Llama, Mistral, DeepSeek, Qwen, Ollama-based models, and other assistants without compatible skill discovery:

1. Open `UNIVERSAL_PROMPT.md`.
2. Copy the fenced prompt into the product's system instructions, custom instructions, project instructions, or initial context.
3. Keep the host's own permission prompts enabled. The prompt does not create a technical sandbox by itself.

For an LLM API, load the fenced prompt as the system or developer message. Tool permissions must still be enforced by the surrounding application.

## Compatibility promise

The governance workflow is model-neutral. Native installation commands are supplied only for hosts verified to support the format. Other models use the universal prompt fallback; this is behavioral guidance, not a claim that every host provides identical tool enforcement.

