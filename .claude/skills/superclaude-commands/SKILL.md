# Skill: SuperClaude Slash Commands

## Purpose
Provides a slash-command system (`agents/commands.py`) for AI agent orchestration.
Commands can be registered, enabled/disabled, role-gated, and chained with pre/post hooks.

## Usage
```python
from agents.commands import CommandDispatcher, Command, CommandCategory

d = CommandDispatcher()
d.register(Command(
    name="deploy", description="Deploy the app",
    handler=lambda args: "deploying...",
    roles=["admin"],
    category=CommandCategory.ADMIN,
))
result = d.dispatch("/deploy staging", user_roles=["admin"])
```

## Key Classes
- **Command** — single slash command with handler, roles, aliases, hooks
- **CommandDispatcher** — registry, alias resolution, role-gated dispatch
- **CommandCategory** — SYSTEM, AGENT, WORKFLOW, UTILITY, ADMIN

## Testing
```bash
python -m pytest tests/test_commands.py -v
```

## Related Issues
- Issue #265: SuperClaude Slash Commands
