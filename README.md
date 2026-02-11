# Loom MCP Server

[MCP](https://modelcontextprotocol.io) server exposing 58 tools for Loom's internal GraphQL API. Works with Claude, Cursor, or any MCP-compatible client.

## Setup

### 1. Auth (pick one)

1. Open Loom in your browser, open DevTools → Application → Cookies
2. Copy the `connect.sid` value
3. Set `LOOM_COOKIE` in your MCP config (see below)

### 2. Install and run

```sh
git clone git@github.com:karbassi/loom-mcp.git
cd loom-mcp
uv sync
uv run loom-mcp
```

### 3. MCP client configuration

**Via uvx (no clone needed):**

```json
{
  "mcpServers": {
    "loom": {
      "type": "stdio",
      "command": "uvx",
      "args": ["--from", "git+https://github.com/karbassi/loom-mcp.git", "loom-mcp"],
      "env": {
        "LOOM_COOKIE": "connect.sid=s%3A..."
      }
    }
  }
}
```

**Via local clone:**

```json
{
  "mcpServers": {
    "loom": {
      "type": "stdio",
      "command": "uv",
      "args": ["run", "--directory", "/path/to/loom-mcp", "loom-mcp"],
      "env": {
        "LOOM_COOKIE": "connect.sid=s%3A..."
      }
    }
  }
}
```

Auth: set `LOOM_COOKIE` in your MCP client config or as an environment variable.

## Tools

### Read (29 tools)

| Tool | Description |
|---|---|
| `list_videos` | List your videos, sorted by most recent |
| `search_videos` | AI-powered semantic search |
| `get_video` | Video metadata (name, duration, owner, views) |
| `get_transcript` | Full transcript with timestamps and speakers |
| `get_captions` | WebVTT captions with start+end timestamps per cue |
| `get_summary` | AI-generated summary |
| `get_chapters` | AI-generated chapters |
| `get_description` | AI-generated detailed description with timestamped sections |
| `get_key_takeaways` | AI-generated key takeaways |
| `get_comments` | Comments and replies |
| `get_tasks` | AI-generated action items |
| `get_reactions` | Emoji reactions |
| `get_tags` | Video tags |
| `get_backlinks` | External references (where the video is shared/embedded) |
| `get_meeting_notes` | Confluence meeting notes URL |
| `get_confluence_pages` | Linked Confluence pages |
| `get_download_url` | Signed MP4 download URL |
| `get_video_details` | All-in-one: metadata + transcript + chapters + summary + comments + tasks |
| `list_folders` | List your folders |
| `list_spaces` | List your workspaces |
| `search_folders` | Search folders by name |
| `get_folder` | Folder details |
| `get_last_watch_time` | Last timestamp where you stopped watching |
| `get_watch_later_count` | Number of videos in your Watch Later list |
| `get_total_videos_count` | Total videos created by a user |
| `get_frequent_reactions` | Your most-used emoji reaction types |
| `get_comment_reactions` | Emoji reactions on a specific comment |
| `get_user` | User profile by ID (name, email, company, avatar) |
| `search_workspace_tags` | Search tags in your workspace |

### Write (29 tools)

| Tool | Description |
|---|---|
| `update_video_name` | Rename a video |
| `update_video_description` | Update video description |
| `create_comment` | Post a comment (with optional timestamp) |
| `edit_comment` | Edit an existing comment |
| `delete_comment` | Delete a comment |
| `create_task` | Create an action item on a video |
| `delete_task` | Delete an action item |
| `approve_task` | Mark a task as approved |
| `respond_to_task` | Respond to a task |
| `add_reaction` | Add an emoji reaction at a timestamp |
| `delete_reaction` | Delete a reaction |
| `toggle_following` | Follow/unfollow a video |
| `archive_videos` | Archive or unarchive videos |
| `duplicate_video` | Duplicate a video |
| `delete_video` | Permanently delete a video |
| `add_to_watch_later` | Add to Watch Later list |
| `remove_from_watch_later` | Remove from Watch Later list |
| `create_folder` | Create a new folder |
| `rename_folder` | Rename a folder |
| `delete_folders` | Delete folders |
| `move_videos` | Move videos to a different folder |
| `move_folders` | Move folders into a different parent folder |
| `recover_video` | Recover a deleted video from trash |
| `pin_video` | Pin or unpin a video in your library |
| `add_comment_reaction` | React to a comment with an emoji |
| `toggle_following_tag` | Follow/unfollow a workspace tag |
| `share_videos_to_spaces` | Share videos to one or more spaces |
| `update_video_settings` | Update video settings (downloads, comments, etc.) |
| `update_task` | Update the content of an action item |

## Auth errors

If you get auth errors, your session cookie has expired (~30 days). Grab a fresh `connect.sid` from your browser.

## Requirements

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) package manager
