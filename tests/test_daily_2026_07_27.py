"""Tests for the 2026-07-27 daily automation run.

Features covered:
  1. Self-healing agent: infrastructure error classification
     - ``ServerSelectionTimeoutError`` / ``Connection refused`` → INFRASTRUCTURE_ERROR
     - Infrastructure errors do NOT dispatch a code fix (they are escalated immediately)
     - Existing categories are not disturbed
  2. MCP tool annotations helpers (MCP spec 2025-11-05 §5.6.1)
     - ``ToolAnnotations`` dataclass
     - ``get_tool_annotations()`` extracts per-tool hints
     - ``filter_safe_tools()`` returns only definitively safe tools
     - Edge cases: missing tool, empty annotations, partial annotations
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ─── 1. Self-healing: infrastructure error classification ─────────────────────

class TestSelfHealingInfrastructureClassification:
    """_classify_failure correctly identifies infrastructure errors."""

    def _classify(self, text: str):
        from agent.self_healing import SelfHealingAgent
        return SelfHealingAgent._classify_failure(text)

    def test_mongodb_server_selection_timeout(self):
        from agent.self_healing import FailureCategory
        err = (
            "pymongo.errors.ServerSelectionTimeoutError: localhost:27017: "
            "[Errno 111] Connection refused, Timeout: 2.0s"
        )
        assert self._classify(err) is FailureCategory.INFRASTRUCTURE_ERROR

    def test_mongo_connection_refused_errno_111(self):
        from agent.self_healing import FailureCategory
        err = "localhost:27017: [Errno 111] Connection refused"
        assert self._classify(err) is FailureCategory.INFRASTRUCTURE_ERROR

    def test_redis_connection_error(self):
        from agent.self_healing import FailureCategory
        err = "redis.exceptions.RedisError: Error 111 connecting to localhost:6379. Connection refused."
        assert self._classify(err) is FailureCategory.INFRASTRUCTURE_ERROR

    def test_postgres_psycopg_error(self):
        from agent.self_healing import FailureCategory
        err = "psycopg2.OperationalError: could not connect to server: Connection refused"
        assert self._classify(err) is FailureCategory.INFRASTRUCTURE_ERROR

    def test_docker_daemon_unavailable(self):
        from agent.self_healing import FailureCategory
        err = "Cannot connect to the Docker daemon at unix:///var/run/docker.sock"
        assert self._classify(err) is FailureCategory.INFRASTRUCTURE_ERROR

    def test_econnrefused(self):
        from agent.self_healing import FailureCategory
        err = "Error: connect ECONNREFUSED 127.0.0.1:5432"
        assert self._classify(err) is FailureCategory.INFRASTRUCTURE_ERROR

    def test_service_unavailable_header(self):
        from agent.self_healing import FailureCategory
        err = "503 Service Unavailable: the upstream container is not running"
        assert self._classify(err) is FailureCategory.INFRASTRUCTURE_ERROR

    def test_mongoclient_keyword(self):
        from agent.self_healing import FailureCategory
        err = "MongoClient failed to connect after 30 seconds"
        assert self._classify(err) is FailureCategory.INFRASTRUCTURE_ERROR

    # Infrastructure check fires BEFORE timeout / network so it is never mis-classified.

    def test_infra_beats_timeout_classifier(self):
        """MongoDB timeout is an infra error, not a generic timeout."""
        from agent.self_healing import FailureCategory
        err = (
            "ServerSelectionTimeoutError: localhost:27017 timed out "
            "after 2.0s — connection refused"
        )
        result = self._classify(err)
        assert result is FailureCategory.INFRASTRUCTURE_ERROR
        assert result is not FailureCategory.TIMEOUT

    def test_infra_beats_network_classifier(self):
        """MongoDB 'connection refused' is infra, not generic network."""
        from agent.self_healing import FailureCategory
        err = "ServerSelectionTimeoutError: connection refused to localhost:27017"
        result = self._classify(err)
        assert result is FailureCategory.INFRASTRUCTURE_ERROR
        assert result is not FailureCategory.NETWORK

    # Existing categories are undisturbed.

    def test_syntax_error_unchanged(self):
        from agent.self_healing import FailureCategory
        assert self._classify("SyntaxError: invalid syntax at line 42") is FailureCategory.SYNTAX_ERROR

    def test_import_error_unchanged(self):
        from agent.self_healing import FailureCategory
        assert self._classify("ModuleNotFoundError: No module named 'foo'") is FailureCategory.IMPORT_ERROR

    def test_test_failure_unchanged(self):
        from agent.self_healing import FailureCategory
        assert self._classify("test_foo failed with AssertionError") is FailureCategory.TEST_FAILURE

    def test_oom_unchanged(self):
        from agent.self_healing import FailureCategory
        assert self._classify("OOM: out of memory, process killed") is FailureCategory.OOM


class TestSelfHealingInfrastructureNoCodeFix:
    """Infrastructure errors reach awaiting_human state without dispatching a fix."""

    @pytest.fixture
    def agent(self):
        from agent.self_healing import SelfHealingAgent
        return SelfHealingAgent()

    @pytest.mark.asyncio
    async def test_mongodb_failure_skips_dispatch(self, agent):
        """on_ci_failure with MongoDB error → awaiting_human, no fix dispatched."""
        from agent.self_healing import HealState

        mongodb_error = (
            "pymongo.errors.ServerSelectionTimeoutError: localhost:27017: "
            "[Errno 111] Connection refused, Timeout: 2.0s"
        )

        with patch.object(agent, "_dispatch_fix", new_callable=AsyncMock) as mock_dispatch:
            event = await agent.on_ci_failure({
                "test": "tests/test_auth_me_regression.py::TestBackendAuthMe::test_valid_token_returns_user_profile",
                "error": mongodb_error,
                "workflow": "ci",
            })

        mock_dispatch.assert_not_called()
        assert event.state == HealState.AWAITING_HUMAN.value

    @pytest.mark.asyncio
    async def test_regular_failure_still_dispatches(self, agent):
        """on_ci_failure with a code error → fix is dispatched."""
        from agent.self_healing import HealState

        with patch.object(agent, "_dispatch_fix", new_callable=AsyncMock) as mock_dispatch:
            event = await agent.on_ci_failure({
                "test": "tests/test_foo.py::test_bar",
                "error": "AssertionError: expected 200, got 500",
                "workflow": "ci",
            })

        mock_dispatch.assert_called_once()

    @pytest.mark.asyncio
    async def test_redis_failure_skips_dispatch(self, agent):
        from agent.self_healing import HealState

        with patch.object(agent, "_dispatch_fix", new_callable=AsyncMock) as mock_dispatch:
            event = await agent.on_ci_failure({
                "test": "tests/test_cache.py::test_write",
                "error": "redis.exceptions.RedisError: Connection refused",
                "workflow": "ci",
            })

        mock_dispatch.assert_not_called()
        assert event.state == HealState.AWAITING_HUMAN.value


class TestSelfHealingInfrastructureHint:
    """_failure_category_hint returns the infrastructure guidance string."""

    def test_infrastructure_hint_present(self):
        from agent.self_healing import SelfHealingAgent
        hint = SelfHealingAgent._failure_category_hint("infrastructure_error")
        assert "infrastructure" in hint.lower() or "external service" in hint.lower()
        assert "code" in hint.lower() or "no code change" in hint.lower()

    def test_existing_hints_unchanged(self):
        from agent.self_healing import SelfHealingAgent
        assert "syntax" in SelfHealingAgent._failure_category_hint("syntax_error").lower()
        assert "timeout" in SelfHealingAgent._failure_category_hint("timeout").lower()


# ─── 2. MCP tool annotations ─────────────────────────────────────────────────

TOOLS_FIXTURE = [
    {
        "name": "read_file",
        "description": "Read a file",
        "inputSchema": {"type": "object", "properties": {"path": {"type": "string"}}},
        "annotations": {
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    },
    {
        "name": "delete_file",
        "description": "Delete a file permanently",
        "inputSchema": {"type": "object", "properties": {"path": {"type": "string"}}},
        "annotations": {
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": False,
            "openWorldHint": False,
        },
    },
    {
        "name": "send_email",
        "description": "Send an email",
        "inputSchema": {"type": "object", "properties": {"to": {"type": "string"}}},
        "annotations": {
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": True,
        },
    },
    {
        "name": "no_annotations",
        "description": "Tool with no annotations block",
        "inputSchema": {"type": "object"},
    },
    {
        "name": "partial_annotations",
        "description": "Tool with partial annotations",
        "inputSchema": {"type": "object"},
        "annotations": {
            "readOnlyHint": True,
        },
    },
]


class TestGetToolAnnotations:
    """get_tool_annotations extracts typed hints."""

    def test_read_only_tool(self):
        from agent.mcp_client import get_tool_annotations
        ann = get_tool_annotations(TOOLS_FIXTURE, "read_file")
        assert ann.read_only_hint is True
        assert ann.destructive_hint is False
        assert ann.idempotent_hint is True
        assert ann.open_world_hint is False

    def test_destructive_tool(self):
        from agent.mcp_client import get_tool_annotations
        ann = get_tool_annotations(TOOLS_FIXTURE, "delete_file")
        assert ann.read_only_hint is False
        assert ann.destructive_hint is True
        assert ann.idempotent_hint is False

    def test_open_world_tool(self):
        from agent.mcp_client import get_tool_annotations
        ann = get_tool_annotations(TOOLS_FIXTURE, "send_email")
        assert ann.open_world_hint is True
        assert ann.destructive_hint is False

    def test_missing_tool_returns_all_none(self):
        from agent.mcp_client import get_tool_annotations
        ann = get_tool_annotations(TOOLS_FIXTURE, "nonexistent_tool")
        assert ann.read_only_hint is None
        assert ann.destructive_hint is None
        assert ann.idempotent_hint is None
        assert ann.open_world_hint is None

    def test_tool_without_annotations_returns_all_none(self):
        from agent.mcp_client import get_tool_annotations
        ann = get_tool_annotations(TOOLS_FIXTURE, "no_annotations")
        assert ann.read_only_hint is None
        assert ann.destructive_hint is None

    def test_partial_annotations_missing_fields_are_none(self):
        from agent.mcp_client import get_tool_annotations
        ann = get_tool_annotations(TOOLS_FIXTURE, "partial_annotations")
        assert ann.read_only_hint is True
        assert ann.destructive_hint is None
        assert ann.idempotent_hint is None
        assert ann.open_world_hint is None

    def test_empty_tool_list(self):
        from agent.mcp_client import get_tool_annotations
        ann = get_tool_annotations([], "read_file")
        assert ann.read_only_hint is None


class TestToolAnnotationsIsSafeToExplore:
    """ToolAnnotations.is_safe_to_explore reflects read-only + non-destructive."""

    def test_read_only_non_destructive_is_safe(self):
        from agent.mcp_client import ToolAnnotations
        ann = ToolAnnotations(read_only_hint=True, destructive_hint=False)
        assert ann.is_safe_to_explore is True

    def test_read_only_none_destructive_is_not_safe(self):
        """Unknown destructive status → not safe."""
        from agent.mcp_client import ToolAnnotations
        ann = ToolAnnotations(read_only_hint=True, destructive_hint=None)
        assert ann.is_safe_to_explore is False

    def test_read_only_false_is_not_safe(self):
        from agent.mcp_client import ToolAnnotations
        ann = ToolAnnotations(read_only_hint=False, destructive_hint=False)
        assert ann.is_safe_to_explore is False

    def test_all_none_is_not_safe(self):
        from agent.mcp_client import ToolAnnotations
        ann = ToolAnnotations()
        assert ann.is_safe_to_explore is False

    def test_destructive_true_overrides_read_only(self):
        from agent.mcp_client import ToolAnnotations
        ann = ToolAnnotations(read_only_hint=True, destructive_hint=True)
        assert ann.is_safe_to_explore is False


class TestFilterSafeTools:
    """filter_safe_tools returns only definitively safe tools."""

    def test_returns_only_read_file(self):
        from agent.mcp_client import filter_safe_tools
        safe = filter_safe_tools(TOOLS_FIXTURE)
        names = {t["name"] for t in safe}
        assert "read_file" in names

    def test_excludes_destructive_tool(self):
        from agent.mcp_client import filter_safe_tools
        safe = filter_safe_tools(TOOLS_FIXTURE)
        names = {t["name"] for t in safe}
        assert "delete_file" not in names

    def test_excludes_open_world_tool(self):
        from agent.mcp_client import filter_safe_tools
        safe = filter_safe_tools(TOOLS_FIXTURE)
        names = {t["name"] for t in safe}
        assert "send_email" not in names

    def test_excludes_no_annotations_tool(self):
        """Unknown safety → excluded."""
        from agent.mcp_client import filter_safe_tools
        safe = filter_safe_tools(TOOLS_FIXTURE)
        names = {t["name"] for t in safe}
        assert "no_annotations" not in names

    def test_excludes_partial_annotations_tool(self):
        """Partial annotations with unknown destructive hint → excluded."""
        from agent.mcp_client import filter_safe_tools
        safe = filter_safe_tools(TOOLS_FIXTURE)
        names = {t["name"] for t in safe}
        assert "partial_annotations" not in names

    def test_empty_tool_list(self):
        from agent.mcp_client import filter_safe_tools
        assert filter_safe_tools([]) == []

    def test_returns_list_type(self):
        from agent.mcp_client import filter_safe_tools
        result = filter_safe_tools(TOOLS_FIXTURE)
        assert isinstance(result, list)
