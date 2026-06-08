#!/usr/bin/env python3
"""CLI tool for managing persistent memories.

Usage:
    python scripts/memory_cli.py save <user_id> <key> <value> [--workspace=<id>] [--tool=<name>]
    python scripts/memory_cli.py recall <user_id> <key> [--workspace=<id>] [--tool=<name>]
    python scripts/memory_cli.py list <user_id> [--workspace=<id>] [--category=<cat>]
    python scripts/memory_cli.py search <user_id> <term> [--workspace=<id>]
    python scripts/memory_cli.py delete <user_id> <key> [--workspace=<id>]
    python scripts/memory_cli.py stats <user_id>
    python scripts/memory_cli.py export <user_id> [--output=<file>] [--workspace=<id>]
    python scripts/memory_cli.py import <user_id> <file> [--workspace=<id>]
    python scripts/memory_cli.py autoload <user_id> [--workspace=<id>] [--tool=<name>]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.persistent_memory import (
    MemoryCategory,
    MemoryScope,
    PersistentMemoryStore,
)


def cmd_save(args: argparse.Namespace, store: PersistentMemoryStore) -> int:
    """Save a memory entry."""
    category = MemoryCategory(args.category) if args.category else MemoryCategory.CONTEXT
    scope = MemoryScope(args.scope) if args.scope else MemoryScope.GLOBAL
    
    store.save(
        user_id=args.user_id,
        key=args.key,
        value=args.value,
        category=category,
        scope=scope,
        workspace_id=args.workspace,
        tool_name=args.tool,
        priority=args.priority,
        tags=args.tags.split(",") if args.tags else None,
    )
    print(f"✓ Saved memory: {args.key}")
    return 0


def cmd_recall(args: argparse.Namespace, store: PersistentMemoryStore) -> int:
    """Recall a memory entry."""
    value = store.recall(
        user_id=args.user_id,
        key=args.key,
        workspace_id=args.workspace,
        tool_name=args.tool,
    )
    if value:
        print(f"{args.key}: {value}")
        return 0
    else:
        print(f"✗ Memory not found: {args.key}", file=sys.stderr)
        return 1


def cmd_list(args: argparse.Namespace, store: PersistentMemoryStore) -> int:
    """List memories."""
    if args.category:
        memories = store.get_memories_by_category(
            user_id=args.user_id,
            category=MemoryCategory(args.category),
            workspace_id=args.workspace,
        )
    else:
        memories = store.auto_load_memories(
            user_id=args.user_id,
            workspace_id=args.workspace,
            max_memories=args.limit,
        )
    
    if not memories:
        print("No memories found.")
        return 0
    
    print(f"Found {len(memories)} memories:\n")
    for key, value in memories.items():
        # Truncate long values
        display_value = value if len(value) <= 80 else value[:77] + "..."
        print(f"  {key}: {display_value}")
    
    return 0


def cmd_search(args: argparse.Namespace, store: PersistentMemoryStore) -> int:
    """Search memories."""
    entries = store.search_memories(
        user_id=args.user_id,
        search_term=args.term,
        workspace_id=args.workspace,
        limit=args.limit,
    )
    
    if not entries:
        print(f"No memories found matching: {args.term}")
        return 0
    
    print(f"Found {len(entries)} matching memories:\n")
    for entry in entries:
        display_value = entry.value if len(entry.value) <= 60 else entry.value[:57] + "..."
        print(f"  [{entry.category}] {entry.key}: {display_value}")
        print(f"    scope={entry.scope} priority={entry.priority} accesses={entry.access_count}")
    
    return 0


def cmd_delete(args: argparse.Namespace, store: PersistentMemoryStore) -> int:
    """Delete a memory entry."""
    deleted = store.delete(
        user_id=args.user_id,
        key=args.key,
        workspace_id=args.workspace,
        tool_name=args.tool,
    )
    if deleted:
        print(f"✓ Deleted memory: {args.key}")
        return 0
    else:
        print(f"✗ Memory not found: {args.key}", file=sys.stderr)
        return 1


def cmd_stats(args: argparse.Namespace, store: PersistentMemoryStore) -> int:
    """Show memory statistics."""
    stats = store.get_memory_stats(args.user_id)
    
    print(f"Memory Statistics for {args.user_id}:\n")
    print(f"  Total memories: {stats['total_memories']}")
    print(f"  Workspaces: {stats['workspaces']}")
    print(f"  Tools: {stats['tools']}")
    print(f"  Total accesses: {stats['total_accesses']}")
    print(f"  Avg priority: {stats['avg_priority']}")
    print(f"\nCategory breakdown:")
    for category, count in stats['category_breakdown'].items():
        print(f"  {category}: {count}")
    
    return 0


def cmd_export(args: argparse.Namespace, store: PersistentMemoryStore) -> int:
    """Export memories to JSON file."""
    data = store.export_memories(
        user_id=args.user_id,
        workspace_id=args.workspace,
    )
    
    output_file = args.output or f"memories_{args.user_id}.json"
    with open(output_file, "w") as f:
        json.dump(data, f, indent=2)
    
    print(f"✓ Exported {data['count']} memories to {output_file}")
    return 0


def cmd_import(args: argparse.Namespace, store: PersistentMemoryStore) -> int:
    """Import memories from JSON file."""
    with open(args.file) as f:
        data = json.load(f)
    
    memories = {m["key"]: m["value"] for m in data.get("memories", [])}
    count = store.bulk_import(
        user_id=args.user_id,
        memories=memories,
        workspace_id=args.workspace,
    )
    
    print(f"✓ Imported {count} memories")
    return 0


def cmd_autoload(args: argparse.Namespace, store: PersistentMemoryStore) -> int:
    """Test auto-load functionality."""
    memories = store.auto_load_memories(
        user_id=args.user_id,
        workspace_id=args.workspace,
        tool_name=args.tool,
        max_memories=args.limit,
    )
    
    print(f"Auto-loaded {len(memories)} memories:\n")
    for key, value in memories.items():
        display_value = value if len(value) <= 80 else value[:77] + "..."
        print(f"  {key}: {display_value}")
    
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Persistent memory management CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    subparsers.required = True
    
    # Save command
    save_parser = subparsers.add_parser("save", help="Save a memory entry")
    save_parser.add_argument("user_id", help="User ID (email)")
    save_parser.add_argument("key", help="Memory key")
    save_parser.add_argument("value", help="Memory value")
    save_parser.add_argument("--workspace", help="Workspace ID")
    save_parser.add_argument("--tool", help="Tool name")
    save_parser.add_argument("--category", help="Memory category", choices=[c.value for c in MemoryCategory])
    save_parser.add_argument("--scope", help="Memory scope", choices=[s.value for s in MemoryScope])
    save_parser.add_argument("--priority", type=int, default=5, help="Priority (1-10)")
    save_parser.add_argument("--tags", help="Comma-separated tags")
    save_parser.set_defaults(func=cmd_save)
    
    # Recall command
    recall_parser = subparsers.add_parser("recall", help="Recall a memory entry")
    recall_parser.add_argument("user_id", help="User ID (email)")
    recall_parser.add_argument("key", help="Memory key")
    recall_parser.add_argument("--workspace", help="Workspace ID")
    recall_parser.add_argument("--tool", help="Tool name")
    recall_parser.set_defaults(func=cmd_recall)
    
    # List command
    list_parser = subparsers.add_parser("list", help="List memories")
    list_parser.add_argument("user_id", help="User ID (email)")
    list_parser.add_argument("--workspace", help="Workspace ID")
    list_parser.add_argument("--category", help="Filter by category", choices=[c.value for c in MemoryCategory])
    list_parser.add_argument("--limit", type=int, default=50, help="Max memories to show")
    list_parser.set_defaults(func=cmd_list)
    
    # Search command
    search_parser = subparsers.add_parser("search", help="Search memories")
    search_parser.add_argument("user_id", help="User ID (email)")
    search_parser.add_argument("term", help="Search term")
    search_parser.add_argument("--workspace", help="Workspace ID")
    search_parser.add_argument("--limit", type=int, default=20, help="Max results")
    search_parser.set_defaults(func=cmd_search)
    
    # Delete command
    delete_parser = subparsers.add_parser("delete", help="Delete a memory entry")
    delete_parser.add_argument("user_id", help="User ID (email)")
    delete_parser.add_argument("key", help="Memory key")
    delete_parser.add_argument("--workspace", help="Workspace ID")
    delete_parser.add_argument("--tool", help="Tool name")
    delete_parser.set_defaults(func=cmd_delete)
    
    # Stats command
    stats_parser = subparsers.add_parser("stats", help="Show memory statistics")
    stats_parser.add_argument("user_id", help="User ID (email)")
    stats_parser.set_defaults(func=cmd_stats)
    
    # Export command
    export_parser = subparsers.add_parser("export", help="Export memories to JSON")
    export_parser.add_argument("user_id", help="User ID (email)")
    export_parser.add_argument("--output", help="Output file path")
    export_parser.add_argument("--workspace", help="Workspace ID")
    export_parser.set_defaults(func=cmd_export)
    
    # Import command
    import_parser = subparsers.add_parser("import", help="Import memories from JSON")
    import_parser.add_argument("user_id", help="User ID (email)")
    import_parser.add_argument("file", help="JSON file to import")
    import_parser.add_argument("--workspace", help="Workspace ID")
    import_parser.set_defaults(func=cmd_import)
    
    # Autoload command
    autoload_parser = subparsers.add_parser("autoload", help="Test auto-load")
    autoload_parser.add_argument("user_id", help="User ID (email)")
    autoload_parser.add_argument("--workspace", help="Workspace ID")
    autoload_parser.add_argument("--tool", help="Tool name")
    autoload_parser.add_argument("--limit", type=int, default=50, help="Max memories")
    autoload_parser.set_defaults(func=cmd_autoload)
    
    args = parser.parse_args()
    
    # Create store instance
    store = PersistentMemoryStore()
    
    # Run command
    return args.func(args, store)


if __name__ == "__main__":
    sys.exit(main())
