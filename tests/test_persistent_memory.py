"""Tests for persistent memory system."""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from agent.persistent_memory import (
    MemoryCategory,
    MemoryEntry,
    MemoryScope,
    PersistentMemoryStore,
)


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)
    yield db_path
    if db_path.exists():
        db_path.unlink()


@pytest.fixture
def memory_store(temp_db):
    """Create a memory store instance for testing."""
    return PersistentMemoryStore(db_path=temp_db)


def test_save_and_recall_basic(memory_store):
    """Test basic save and recall functionality."""
    memory_store.save(
        user_id="test@example.com",
        key="test_key",
        value="test_value",
    )
    
    value = memory_store.recall(
        user_id="test@example.com",
        key="test_key",
    )
    
    assert value == "test_value"


def test_save_with_workspace_scope(memory_store):
    """Test saving and recalling workspace-scoped memories."""
    memory_store.save(
        user_id="test@example.com",
        key="workspace_setting",
        value="dark_mode",
        scope=MemoryScope.WORKSPACE,
        workspace_id="project-alpha",
    )
    
    # Should find it with correct workspace
    value = memory_store.recall(
        user_id="test@example.com",
        key="workspace_setting",
        workspace_id="project-alpha",
    )
    assert value == "dark_mode"
    
    # Should not find it with wrong workspace
    value = memory_store.recall(
        user_id="test@example.com",
        key="workspace_setting",
        workspace_id="project-beta",
    )
    assert value is None


def test_save_with_tool_scope(memory_store):
    """Test saving and recalling tool-scoped memories."""
    memory_store.save(
        user_id="test@example.com",
        key="editor_theme",
        value="monokai",
        scope=MemoryScope.TOOL,
        tool_name="cursor",
    )
    
    value = memory_store.recall(
        user_id="test@example.com",
        key="editor_theme",
        tool_name="cursor",
    )
    assert value == "monokai"


def test_auto_load_global_memories(memory_store):
    """Test auto-loading global memories."""
    # Save multiple global memories
    memory_store.save("user@example.com", "pref_theme", "dark", priority=8)
    memory_store.save("user@example.com", "pref_lang", "python", priority=7)
    memory_store.save("user@example.com", "context_project", "llm-server", priority=6)
    
    memories = memory_store.auto_load_memories(
        user_id="user@example.com",
        max_memories=10,
    )
    
    assert len(memories) == 3
    assert memories["pref_theme"] == "dark"
    assert memories["pref_lang"] == "python"
    assert memories["context_project"] == "llm-server"


def test_auto_load_with_workspace(memory_store):
    """Test auto-loading includes workspace-specific memories."""
    # Global memory
    memory_store.save(
        "user@example.com",
        "global_pref",
        "value1",
        scope=MemoryScope.GLOBAL,
    )
    
    # Workspace memory
    memory_store.save(
        "user@example.com",
        "workspace_pref",
        "value2",
        scope=MemoryScope.WORKSPACE,
        workspace_id="ws1",
    )
    
    # Auto-load without workspace
    memories = memory_store.auto_load_memories("user@example.com")
    assert len(memories) == 1
    assert "global_pref" in memories
    
    # Auto-load with workspace
    memories = memory_store.auto_load_memories(
        "user@example.com",
        workspace_id="ws1",
    )
    assert len(memories) == 2
    assert "global_pref" in memories
    assert "workspace_pref" in memories


def test_auto_load_priority_ordering(memory_store):
    """Test that auto-load respects priority ordering."""
    memory_store.save("user@example.com", "key1", "low", priority=3)
    memory_store.save("user@example.com", "key2", "high", priority=9)
    memory_store.save("user@example.com", "key3", "med", priority=5)
    
    # Recall to increase access count on key1
    for _ in range(10):
        memory_store.recall("user@example.com", "key1", log_access=True)
    
    memories = memory_store.auto_load_memories("user@example.com", max_memories=2)
    
    # Should get high priority first, then high access count
    assert "key2" in memories  # Highest priority
    # key1 or key3 depending on access count


def test_get_memories_by_category(memory_store):
    """Test filtering memories by category."""
    memory_store.save(
        "user@example.com",
        "pref1",
        "value1",
        category=MemoryCategory.PREFERENCE,
    )
    memory_store.save(
        "user@example.com",
        "ctx1",
        "value2",
        category=MemoryCategory.CONTEXT,
    )
    memory_store.save(
        "user@example.com",
        "learn1",
        "value3",
        category=MemoryCategory.LEARNING,
    )
    
    prefs = memory_store.get_memories_by_category(
        "user@example.com",
        MemoryCategory.PREFERENCE,
    )
    assert len(prefs) == 1
    assert "pref1" in prefs
    
    context = memory_store.get_memories_by_category(
        "user@example.com",
        MemoryCategory.CONTEXT,
    )
    assert len(context) == 1
    assert "ctx1" in context


def test_search_memories(memory_store):
    """Test searching memories."""
    memory_store.save("user@example.com", "python_version", "3.11")
    memory_store.save("user@example.com", "node_version", "20.0")
    memory_store.save("user@example.com", "preferred_language", "python")
    
    results = memory_store.search_memories(
        "user@example.com",
        "python",
    )
    assert len(results) == 2
    keys = [r.key for r in results]
    assert "python_version" in keys
    assert "preferred_language" in keys


def test_delete_memory(memory_store):
    """Test deleting memories."""
    memory_store.save("user@example.com", "temp_key", "temp_value")
    
    # Verify it exists
    assert memory_store.recall("user@example.com", "temp_key") == "temp_value"
    
    # Delete it
    deleted = memory_store.delete("user@example.com", "temp_key")
    assert deleted is True
    
    # Verify it's gone
    assert memory_store.recall("user@example.com", "temp_key") is None
    
    # Delete again should return False
    deleted = memory_store.delete("user@example.com", "temp_key")
    assert deleted is False


def test_bulk_import(memory_store):
    """Test bulk importing memories."""
    memories = {
        "key1": "value1",
        "key2": "value2",
        "key3": "value3",
    }
    
    count = memory_store.bulk_import(
        "user@example.com",
        memories,
        category=MemoryCategory.CONTEXT,
    )
    
    assert count == 3
    assert memory_store.recall("user@example.com", "key1") == "value1"
    assert memory_store.recall("user@example.com", "key2") == "value2"
    assert memory_store.recall("user@example.com", "key3") == "value3"


def test_export_memories(memory_store):
    """Test exporting memories."""
    memory_store.save("user@example.com", "key1", "value1")
    memory_store.save("user@example.com", "key2", "value2", workspace_id="ws1")
    
    # Export all
    data = memory_store.export_memories("user@example.com")
    assert data["count"] == 2
    assert len(data["memories"]) == 2
    
    # Export workspace-specific
    data = memory_store.export_memories("user@example.com", workspace_id="ws1")
    assert data["count"] == 1


def test_get_memory_stats(memory_store):
    """Test memory statistics."""
    memory_store.save(
        "user@example.com",
        "pref1",
        "val1",
        category=MemoryCategory.PREFERENCE,
    )
    memory_store.save(
        "user@example.com",
        "ctx1",
        "val2",
        category=MemoryCategory.CONTEXT,
    )
    memory_store.save(
        "user@example.com",
        "learn1",
        "val3",
        category=MemoryCategory.LEARNING,
        workspace_id="ws1",
    )
    
    # Access some memories
    memory_store.recall("user@example.com", "pref1")
    memory_store.recall("user@example.com", "ctx1")
    
    stats = memory_store.get_memory_stats("user@example.com")
    
    assert stats["total_memories"] == 3
    assert stats["categories"] == 3
    assert stats["workspaces"] >= 1
    assert stats["total_accesses"] >= 2
    assert "preference" in stats["category_breakdown"]
    assert "context" in stats["category_breakdown"]
    assert "learning" in stats["category_breakdown"]


def test_memory_upsert(memory_store):
    """Test that saving the same key updates the value."""
    memory_store.save("user@example.com", "key1", "original")
    assert memory_store.recall("user@example.com", "key1") == "original"
    
    memory_store.save("user@example.com", "key1", "updated")
    assert memory_store.recall("user@example.com", "key1") == "updated"


def test_access_count_tracking(memory_store):
    """Test that access counts are tracked."""
    memory_store.save("user@example.com", "key1", "value1")
    
    # Recall multiple times
    for _ in range(5):
        memory_store.recall("user@example.com", "key1", log_access=True)
    
    # Check stats reflect access count
    stats = memory_store.get_memory_stats("user@example.com")
    assert stats["total_accesses"] == 5


def test_tags_support(memory_store):
    """Test saving and retrieving memories with tags."""
    memory_store.save(
        "user@example.com",
        "tagged_key",
        "tagged_value",
        tags=["important", "python", "config"],
    )
    
    # Search should find tagged memories
    results = memory_store.search_memories("user@example.com", "tagged")
    assert len(results) == 1
    assert results[0].tags == ["important", "python", "config"]
