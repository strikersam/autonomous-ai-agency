# SuperClaude Slash Commands Skill

**Inspired by:** [SuperClaude Framework](https://github.com/SuperClaude-Org/SuperClaude_Framework) — 30+ slash commands for structured development

**Purpose:** Implement a slash command dispatcher system in local-llm-server following SuperClaude's patterns.

## What's Unique About SuperClaude

SuperClaude provides **30+ structured slash commands** across 8 categories:
- `/plan` — architecture and planning
- `/task` — task management
- `/implement` — execution
- `/test` — validation
- `/review` — code review
- `/document` — documentation
- `/research` — information gathering
- `/troubleshoot` — debugging

Each command has structured inputs/outputs, clear use cases, and integration with a PM agent.

## Implementation

Created `agents/commands.py` with:
- **CommandDispatcher** — routes slash commands to handlers
- **8 core commands** — plan, task, implement, test, review, document, research, troubleshoot
- **Command registry** — extensible system for adding commands
- **Aliases** — multiple names per command (e.g., /exec = /implement)

## Usage

```python
from agents.commands import get_dispatcher

dispatcher = get_dispatcher()

# List available commands
commands = dispatcher.list_commands()

# Dispatch a command
result = dispatcher.dispatch("/plan create a caching layer", context={...})

# Register custom command
dispatcher.register(Command(
    name="custom",
    category=CommandCategory.EXECUTION,
    description="Custom command",
    usage="/custom <args>",
    handler=my_handler
))
```

## Integration Points

- **Agent loop** — parse slash commands in user input
- **Backend API** — expose /commands endpoint
- **Chat handlers** — intercept and route slash commands
- **Skills system** — organize commands by domain

## Files

- `agents/commands.py` — main dispatcher (280 LOC)
- `tests/test_commands.py` — test suite (150+ LOC)
- `.claude/skills/superclaudecommands/SKILL.md` — this file

## References

- SuperClaude: https://github.com/SuperClaude-Org/SuperClaude_Framework
- SuperClaude Commands: https://github.com/SuperClaude-Org/SuperClaude_Framework/blob/master/docs/user-guide/commands.md
- Quick-Note Issue: #265
