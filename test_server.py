"""Tests for the Loom MCP server.

Requires: pip install pytest anyio fastmcp
Run:      pytest test_server.py -v
"""

import os
import re

# Set dummy auth so lifespan can initialize without real credentials
os.environ.setdefault("LOOM_COOKIE", "test=dummy")

import pytest
from fastmcp.client import Client

from main import mcp

READ_TOOLS = {
    "list_videos", "search_videos", "get_video", "get_transcript",
    "get_captions", "get_summary", "get_chapters", "get_comments",
    "get_download_url", "get_tasks", "get_reactions", "get_meeting_notes",
    "list_folders", "list_spaces", "get_backlinks", "get_key_takeaways",
    "get_tags", "get_description", "get_confluence_pages", "search_folders",
    "get_last_watch_time", "get_watch_later_count", "get_total_videos_count",
    "get_frequent_reactions", "get_comment_reactions", "get_video_details",
    "get_user", "search_workspace_tags", "get_folder",
}

DESTRUCTIVE_TOOLS = {
    "update_video_name", "update_video_description", "update_video_settings",
    "edit_comment", "delete_comment", "update_task", "delete_task",
    "delete_reaction", "delete_video", "archive_videos",
    "remove_from_watch_later", "rename_folder", "delete_folders",
    "move_videos", "move_folders",
}

CREATE_TOOLS = {
    "create_comment", "create_task", "add_reaction", "duplicate_video",
    "create_folder",
}

IDEMPOTENT_WRITE_TOOLS = {
    "approve_task", "respond_to_task", "toggle_following",
    "add_to_watch_later", "recover_video", "pin_video",
    "add_comment_reaction", "toggle_following_tag", "share_videos_to_spaces",
}

ALL_TOOLS = READ_TOOLS | DESTRUCTIVE_TOOLS | CREATE_TOOLS | IDEMPOTENT_WRITE_TOOLS


@pytest.fixture
async def client():
    async with Client(transport=mcp) as c:
        yield c


@pytest.mark.anyio
async def test_all_tools_registered(client):
    tools = await client.list_tools()
    names = {t.name for t in tools}
    missing = ALL_TOOLS - names
    extra = names - ALL_TOOLS
    assert not missing, f"Missing tools: {missing}"
    assert not extra, f"Unexpected tools: {extra}"


@pytest.mark.anyio
async def test_tool_count(client):
    tools = await client.list_tools()
    assert len(tools) == 58


@pytest.mark.anyio
async def test_read_tools_are_readonly(client):
    tools = await client.list_tools()
    tool_map = {t.name: t for t in tools}
    for name in READ_TOOLS:
        tool = tool_map[name]
        ann = tool.annotations
        assert ann is not None, f"{name} is missing annotations"
        assert ann.readOnlyHint is True, f"{name} should be readOnlyHint=True"
        assert ann.destructiveHint is False, f"{name} should be destructiveHint=False"
        assert ann.idempotentHint is True, f"{name} should be idempotentHint=True"


@pytest.mark.anyio
async def test_destructive_tools_are_marked(client):
    tools = await client.list_tools()
    tool_map = {t.name: t for t in tools}
    for name in DESTRUCTIVE_TOOLS:
        tool = tool_map[name]
        ann = tool.annotations
        assert ann is not None, f"{name} is missing annotations"
        assert ann.readOnlyHint is False, f"{name} should be readOnlyHint=False"
        assert ann.destructiveHint is True, f"{name} should be destructiveHint=True"


@pytest.mark.anyio
async def test_create_tools_are_not_destructive(client):
    tools = await client.list_tools()
    tool_map = {t.name: t for t in tools}
    for name in CREATE_TOOLS:
        tool = tool_map[name]
        ann = tool.annotations
        assert ann is not None, f"{name} is missing annotations"
        assert ann.readOnlyHint is False, f"{name} should be readOnlyHint=False"
        assert ann.destructiveHint is False, f"{name} should be destructiveHint=False"
        assert ann.idempotentHint is False, f"{name} should be idempotentHint=False"


@pytest.mark.anyio
async def test_idempotent_write_tools(client):
    tools = await client.list_tools()
    tool_map = {t.name: t for t in tools}
    for name in IDEMPOTENT_WRITE_TOOLS:
        tool = tool_map[name]
        ann = tool.annotations
        assert ann is not None, f"{name} is missing annotations"
        assert ann.readOnlyHint is False, f"{name} should be readOnlyHint=False"
        assert ann.destructiveHint is False, f"{name} should be destructiveHint=False"
        assert ann.idempotentHint is True, f"{name} should be idempotentHint=True"


@pytest.mark.anyio
async def test_all_tools_have_descriptions(client):
    tools = await client.list_tools()
    for tool in tools:
        assert tool.description, f"{tool.name} is missing a description"
        assert len(tool.description) >= 20, f"{tool.name} description is too short"


@pytest.mark.anyio
async def test_tool_names_are_snake_case(client):
    tools = await client.list_tools()
    for tool in tools:
        assert re.fullmatch(r"[a-z][a-z0-9_]*", tool.name), f"{tool.name} is not snake_case"
