# Persistent Memory System

## Overview

The Persistent Memory System provides AI coding tools with long-term memory that persists across sessions, workspaces, and even different tools. This enables truly contextual AI assistance that remembers your preferences, learns from corrections, and maintains project-specific knowledge.

## Features

### 1. **Semantic Memory Categorization**
Memories are organized into semantic categories for better retrieval:
- **Preferences**: User preferences (coding style, naming conventions, framework choices)
- **Context**: Project/workspace-specific information
- **Learning**: Patterns learned from corrections and feedback
- **History**: Historical decisions and their rationale
- **Tool Config**: Tool-specific configurations

### 2. **Scope-Based Auto-Loading**
Memories can be scoped to control when they're automatically loaded:
- **Global**: Always loaded for the user (e.g., coding style preferences)
- **Workspace**: Loaded only in specific workspaces (e.g., project architecture)
- **Session**: Loaded only in specific agent sessions
- **Tool**: Loaded for specific AI tools (e.g., Cursor-specific settings)

### 3. **Priority-Based Retrieval**
Each memory has a priority (1-10) that determines loading order when the context limit is reached. Higher priority memories are loaded first.

### 4. **Cross-Tool Compatibility**
Automatically detects and adapts to different AI coding tools:
- Claude Code
- Cursor
- VSCode with Continue/Cline
- Zed
- Aider
- OpenAI Codex
- CLI tools

### 5. **Automatic Context Injection**
The memory middleware automatically injects relevant memories into requests without requiring explicit tool configuration changes.

## Architecture

```
┌─────────────────────┐
│   AI Coding Tool    │
│ (Cursor/VSCode/etc) │
└──────────┬──────────┘
           │ HTTP Request
           ▼
┌─────────────────────┐
│ Memory Middleware   │
│ - Detects tool      │
│ - Extracts workspace│
│ - Auto-loads memory │
│ - Injects context   │
└──────────┬──────────┘
           │ Enriched Request
           ▼
┌─────────────────────┐
│  local-llm-server   │
│   Proxy + Router    │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ Persistent Memory   │
│      Store          │
│  (SQLite Backend)   │
└─────────────────────┘
```

## Usage

### CLI Tool

The memory system includes a full-featured CLI for managing memories:

```bash
# Save a memory
python scripts/memory_cli.py save user@example.com my_preference "tabs over spaces" \
  --category=preference --priority=8

# Save workspace-specific memory
python scripts/memory_cli.py save user@example.com architecture "microservices" \
  --workspace=project-alpha --category=context

# Save tool-specific memory
python scripts/memory_cli.py save user@example.com theme "monokai" \
  --tool=cursor --category=tool_config

# Recall a memory
python scripts/memory_cli.py recall user@example.com my_preference

# List all memories
python scripts/memory_cli.py list user@example.com

# Search memories
python scripts/memory_cli.py search user@example.com "python"

# View statistics
python scripts/memory_cli.py stats user@example.com

# Export memories
python scripts/memory_cli.py export user@example.com --output=backup.json

# Import memories
python scripts/memory_cli.py import user@example.com backup.json

# Test auto-load
python scripts/memory_cli.py autoload user@example.com \
  --workspace=my-project --tool=cursor
```

### Python API

```python
from agent.persistent_memory import (
    PersistentMemoryStore,
    MemoryCategory,
    MemoryScope,
)

# Initialize store
store = PersistentMemoryStore()

# Save memories
store.save(
    user_id="user@example.com",
    key="coding_style",
    value="functional with type hints",
    category=MemoryCategory.PREFERENCE,
    scope=MemoryScope.GLOBAL,
    priority=9,
    tags=["python", "style"],
)

# Auto-load relevant memories
memories = store.auto_load_memories(
    user_id="user@example.com",
    workspace_id="my-project",
    tool_name="cursor",
    max_memories=50,
)

# Search memories
results = store.search_memories(
    user_id="user@example.com",
    search_term="python",
    limit=20,
)

# Get memories by category
preferences = store.get_memories_by_category(
    user_id="user@example.com",
    category=MemoryCategory.PREFERENCE,
)
```

### Memory Middleware

The middleware automatically injects memories into AI tool requests:

```python
from agent.memory_middleware import MemoryMiddleware

middleware = MemoryMiddleware()

# Process a chat request
enriched_request = middleware.process_request(
    request_data={
        "messages": [...],
        "metadata": {"workspace_id": "my-project"},
    },
    user_id="user@example.com",
    headers={"user-agent": "cursor/1.0"},
)

# Save learnings from response
middleware.save_from_response(
    response=model_response,
    user_id="user@example.com",
    workspace_id="my-project",
)
```

## Configuration

### Environment Variables

```bash
# Enable/disable auto-loading (default: true)
MEMORY_AUTOLOAD_ENABLED=true

# Maximum memories to auto-load (default: 50)
MEMORY_AUTOLOAD_MAX=50

# Database path (default: .data/agent.db)
AGENT_DB_PATH=/path/to/memory.db
```

### Integration with proxy.py

The memory middleware is automatically integrated into the chat handlers. No configuration changes needed for basic functionality.

## Client Tool Setup

### Cursor

Add to your `.cursor/settings.json`:
```json
{
  "api.baseURL": "http://localhost:8000/v1",
  "api.headers": {
    "X-Tool": "cursor"
  }
}
```

### VSCode with Continue

Update `.continue/config.json`:
```json
{
  "models": [{
    "title": "Local LLM",
    "provider": "openai",
    "apiBase": "http://localhost:8000/v1",
    "model": "qwen3-coder:30b",
    "extraHeaders": {
      "X-Tool": "continue"
    }
  }]
}
```

### Claude Code

Set environment variable:
```bash
export ANTHROPIC_BASE_URL=http://localhost:8000/v1
export ANTHROPIC_API_KEY=your-key
```

Headers are automatically detected from the Claude Code user agent.

### Zed

Configure in `~/.config/zed/settings.json`:
```json
{
  "assistant": {
    "provider": {
      "type": "openai",
      "api_url": "http://localhost:8000/v1",
      "model": "qwen3-coder:30b",
      "extra_headers": {
        "X-Tool": "zed"
      }
    }
  }
}
```

### Aider

```bash
aider --openai-api-base http://localhost:8000/v1 \
  --model qwen3-coder:30b \
  --extra-headers '{"X-Tool": "aider"}'
```

## Best Practices

### 1. **Use Appropriate Scopes**
- Global scope for universal preferences (coding style, language preferences)
- Workspace scope for project-specific context (architecture decisions, conventions)
- Tool scope for tool-specific settings (editor themes, keybindings)

### 2. **Prioritize Effectively**
- Priority 9-10: Critical preferences that should always be loaded
- Priority 7-8: Important context that's frequently relevant
- Priority 5-6: Standard context and learning
- Priority 1-4: Nice-to-have context, loaded if space permits

### 3. **Use Semantic Categories**
- Preferences: Things that define "how you like to work"
- Context: Facts about the project/workspace
- Learning: Corrections and patterns to avoid repeating mistakes
- History: Why decisions were made (for future reference)

### 4. **Tag Liberally**
Tags make searching easier:
```python
store.save(
    user_id="user@example.com",
    key="test_framework",
    value="pytest with fixtures",
    tags=["testing", "python", "pytest", "ci"],
)
```

### 5. **Periodic Cleanup**
Use the stats and search features to identify stale memories:
```bash
# View stats
python scripts/memory_cli.py stats user@example.com

# Search for old project references
python scripts/memory_cli.py search user@example.com "old-project"

# Delete if no longer relevant
python scripts/memory_cli.py delete user@example.com old_project_arch
```

## Advanced Features

### Learning from Responses

The middleware can extract and save memories from model responses using special markers:

```
[MEMORY:preferred_error_handling=try/except with specific exceptions]
[MEMORY:api_style=RESTful with OpenAPI docs]
```

These markers are automatically parsed and saved as learning memories.

### Memory Export/Import

Backup and restore memories:
```bash
# Export
python scripts/memory_cli.py export user@example.com --output=backup.json

# Import (e.g., to new machine)
python scripts/memory_cli.py import user@example.com backup.json
```

### Access Analytics

The system tracks how often memories are accessed, which influences auto-loading priority:
```bash
python scripts/memory_cli.py stats user@example.com
```

Shows:
- Total memories
- Access counts
- Category breakdown
- Workspace distribution

## Schema

### persistent_memories table
```sql
CREATE TABLE persistent_memories (
    user_id TEXT NOT NULL,
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'context',
    scope TEXT NOT NULL DEFAULT 'global',
    workspace_id TEXT,
    tool_name TEXT,
    priority INTEGER NOT NULL DEFAULT 5,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    access_count INTEGER NOT NULL DEFAULT 0,
    tags TEXT DEFAULT '[]',
    PRIMARY KEY (user_id, key, scope, COALESCE(workspace_id, ''), COALESCE(tool_name, ''))
)
```

## Migration from Legacy Memory

If you're using the old `UserMemoryStore`, you can migrate:

```python
from agent.user_memory import UserMemoryStore
from agent.persistent_memory import PersistentMemoryStore, MemoryCategory

old_store = UserMemoryStore()
new_store = PersistentMemoryStore()

# Get all old memories
old_memories = old_store.recall_all("user@example.com")

# Import to new store
new_store.bulk_import(
    user_id="user@example.com",
    memories=old_memories,
    category=MemoryCategory.CONTEXT,
)
```

## Troubleshooting

### Memories Not Loading
1. Check that `MEMORY_AUTOLOAD_ENABLED=true`
2. Verify user_id matches (email-based)
3. Check workspace_id is being detected
4. Inspect middleware logs: `grep "auto-loaded" logs/proxy.log`

### Database Locked
If you see "database is locked" errors:
1. Check no other processes are accessing the DB
2. The system automatically falls back to MEMORY journal mode
3. On problematic filesystems (virtiofs, NFS), it falls back to /tmp

### Too Many/Few Memories
Adjust `MEMORY_AUTOLOAD_MAX`:
```bash
export MEMORY_AUTOLOAD_MAX=100  # Load up to 100 memories
```

Or adjust priority values to control what gets loaded first.

## Future Enhancements

Planned improvements:
- [ ] Semantic similarity search using embeddings
- [ ] Automatic memory summarization for long values
- [ ] Memory version history and rollback
- [ ] Cross-user memory sharing (for teams)
- [ ] Memory conflict resolution
- [ ] Redis backend option for distributed deployments
- [ ] Memory compression for large values
- [ ] Time-based memory expiration
- [ ] Machine learning for memory relevance scoring

## API Reference

See the inline documentation in:
- `agent/persistent_memory.py` - Core store implementation
- `agent/memory_middleware.py` - Auto-injection middleware
- `scripts/memory_cli.py` - CLI tool
