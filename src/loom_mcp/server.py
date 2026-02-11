import json
import os
import re
from pathlib import Path
from typing import Annotated

from fastmcp import FastMCP, Context
from fastmcp.exceptions import ToolError
from fastmcp.server.lifespan import lifespan
from pydantic import Field

from loom_mcp.client import LoomClient, LoomAPIError

_ID_RE = re.compile(r"\A[a-zA-Z0-9_.\-]{1,200}\Z")


def _find_project_root() -> Path:
    d = Path(__file__).resolve().parent
    while d != d.parent:
        if (d / "pyproject.toml").exists():
            return d
        d = d.parent
    return Path.cwd()


_REPO_ROOT = _find_project_root().parent  # loom-api/

# Load .env from parent repo (no dependencies)
_env_path = _REPO_ROOT / ".env"
if _env_path.exists():
    for _line in _env_path.read_text().splitlines():
        if _line.strip() and not _line.startswith("#") and "=" in _line:
            _k, _, _v = _line.partition("=")
            os.environ.setdefault(_k.strip(), _v.strip().strip("'\""))


@lifespan
async def app_lifespan(server):
    cookie = os.environ.get("LOOM_COOKIE")
    if cookie:
        client = LoomClient(cookies=cookie)
    else:
        auth_file = os.environ.get(
            "LOOM_AUTH_FILE",
            str(_REPO_ROOT / "auth.json"),
        )
        client = LoomClient(auth_file=auth_file)
    try:
        yield {"loom": client}
    finally:
        await client.aclose()


mcp = FastMCP(
    "Loom",
    instructions="Access Loom videos, transcripts, summaries, and comments.",
    lifespan=app_lifespan,
    version="0.1.0",
)


def _get_client(ctx: Context) -> LoomClient:
    return ctx.lifespan_context["loom"]


async def _call(coro):
    """Await a client coroutine, converting LoomAPIError to ToolError."""
    try:
        return await coro
    except LoomAPIError as e:
        raise ToolError(str(e)) from None


def _id(value: str, label: str = "ID") -> str:
    """Validate a single resource ID."""
    if not _ID_RE.fullmatch(value):
        raise ToolError(f"Invalid {label}: {value!r}")
    return value


def _ids(values: list[str], label: str = "ID") -> list[str]:
    """Validate a list of resource IDs."""
    for v in values:
        _id(v, label)
    return values


# ---------------------------------------------------------------------------
# Read Tools
# ---------------------------------------------------------------------------


@mcp.tool(
    tags={"read"},
    timeout=30.0,
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
    },
)
async def list_videos(
    ctx: Context,
    limit: Annotated[
        int, Field(description="Max videos to return (default 50)", ge=1, le=200)
    ] = 50,
) -> str:
    """List your Loom videos, sorted by most recent.

    Returns video IDs and names. Use get_video for metadata on a specific video,
    or get_video_details for comprehensive info including transcript and comments.
    """
    client = _get_client(ctx)
    videos = []
    cursor = None
    while len(videos) < limit:
        batch_size = min(50, limit - len(videos))
        result = await _call(client.list_videos(limit=batch_size, cursor=cursor))
        videos.extend(result["videos"])
        if not result["hasNextPage"]:
            break
        cursor = result["endCursor"]
    lines = [f"{v['id']}  {v['name']}" for v in videos]
    return f"Found {len(videos)} videos:\n\n" + "\n".join(lines)


@mcp.tool(
    tags={"read"},
    timeout=30.0,
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
    },
)
async def search_videos(
    ctx: Context,
    query: Annotated[str, "Search query — supports natural language / semantic search"],
) -> str:
    """Search Loom videos using AI-powered semantic search.

    Understands natural language queries, not just keywords. Returns matching video IDs and names.
    """
    client = _get_client(ctx)
    matches = await _call(client.search_videos(query))
    if not matches:
        return f"No videos matching '{query}'"
    lines = [f"{v['id']}  {v['name']}" for v in matches]
    return f"Found {len(matches)} matching videos:\n\n" + "\n".join(lines)


@mcp.tool(
    tags={"read"},
    timeout=30.0,
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
    },
)
async def get_video(
    ctx: Context,
    video_id: Annotated[str, "The Loom video ID (32-char hex string)"],
) -> str:
    """Get metadata for a Loom video including name, duration, owner, views, and creation date.

    For comprehensive info including transcript, chapters, summary, and comments in one call,
    use get_video_details instead.
    """
    client = _get_client(ctx)
    video = await _call(client.get_video(_id(video_id, "video ID")))
    if video.get("message"):
        raise ToolError(f"Cannot access video {video_id}: {video['message']}")
    return json.dumps(video, indent=2)


@mcp.tool(
    tags={"read"},
    timeout=30.0,
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
    },
)
async def get_transcript(
    ctx: Context,
    video_id: Annotated[str, "The Loom video ID"],
) -> str:
    """Get the full transcript of a Loom video with timestamps and speaker names.

    Returns plain text with one line per phrase. For precise start/end timing per cue
    in WebVTT format, use get_captions instead.
    """
    client = _get_client(ctx)
    text = await _call(client.get_transcript_text(_id(video_id, "video ID")))
    if not text:
        return "No transcript available for this video."
    return text


@mcp.tool(
    tags={"read"},
    timeout=30.0,
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
    },
)
async def get_captions(
    ctx: Context,
    video_id: Annotated[str, "The Loom video ID"],
) -> str:
    """Get WebVTT captions of a Loom video with start and end timestamps per cue.

    Ideal for precise timing analysis. For plain text with speaker names, use get_transcript instead.
    """
    client = _get_client(ctx)
    vtt = await _call(client.get_captions(_id(video_id, "video ID")))
    if not vtt:
        return "No captions available for this video."
    return vtt


@mcp.tool(
    tags={"read"},
    timeout=30.0,
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
    },
)
async def get_summary(
    ctx: Context,
    video_id: Annotated[str, "The Loom video ID"],
) -> str:
    """Get the AI-generated summary of a Loom video (1-2 concise sentences).

    For a detailed timestamped breakdown with bullet points, use get_description.
    For key highlights as a bullet list, use get_key_takeaways.
    For chapter markers, use get_chapters.
    """
    client = _get_client(ctx)
    summary = await _call(client.get_summary(_id(video_id, "video ID")))
    if not summary or not summary.get("autoDescription"):
        return "No AI summary available for this video."
    return summary["autoDescription"]


@mcp.tool(
    tags={"read"},
    timeout=30.0,
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
    },
)
async def get_chapters(
    ctx: Context,
    video_id: Annotated[str, "The Loom video ID"],
) -> str:
    """Get AI-generated chapter markers with timestamps for a Loom video.

    Useful for navigating long videos. For a narrative summary, use get_summary.
    """
    client = _get_client(ctx)
    chapters = await _call(client.get_chapters(_id(video_id, "video ID")))
    if not chapters or not chapters.get("content"):
        return "No chapters available for this video."
    return chapters["content"]


@mcp.tool(
    tags={"read"},
    timeout=30.0,
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
    },
)
async def get_comments(
    ctx: Context,
    video_id: Annotated[str, "The Loom video ID"],
) -> str:
    """Get comments on a Loom video, including threaded replies and timestamps."""
    client = _get_client(ctx)
    comments = await _call(client.get_comments(_id(video_id, "video ID")))
    if not comments:
        return "No comments on this video."
    lines = []
    for c in comments:
        ts = f" @{c['time_stamp']}s" if c.get("time_stamp") is not None else ""
        lines.append(f"[{c['user_name']}{ts}] {c['content']}")
        for r in c.get("children_comments") or []:
            lines.append(f"  └─ [{r['user_name']}] {r['content']}")
    return "\n".join(lines)


@mcp.tool(
    tags={"read"},
    timeout=30.0,
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
    },
)
async def get_download_url(
    ctx: Context,
    video_id: Annotated[str, "The Loom video ID"],
) -> str:
    """Get a signed download URL for the MP4 file of a Loom video. The URL is temporary and will expire."""
    client = _get_client(ctx)
    url = await _call(client.get_download_url(_id(video_id, "video ID")))
    if not url:
        return "No download URL available for this video."
    return url


@mcp.tool(
    tags={"read"},
    timeout=30.0,
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
    },
)
async def get_tasks(
    ctx: Context,
    video_id: Annotated[str, "The Loom video ID"],
) -> str:
    """Get AI-generated action items (tasks) from a Loom video, including assignee, status, and timestamp."""
    client = _get_client(ctx)
    tasks = await _call(client.get_tasks(_id(video_id, "video ID")))
    if not tasks:
        return "No tasks/action items for this video."
    lines = []
    for t in tasks:
        owner = (t.get("owner") or {}).get("display_name", "Unassigned")
        ts = f" @{t['time_stamp']}s" if t.get("time_stamp") is not None else ""
        status = "resolved" if t.get("resolved_at") else "open"
        lines.append(f"[{status}] [{owner}{ts}] {t['content']}")
    return "\n".join(lines)


@mcp.tool(
    tags={"read"},
    timeout=30.0,
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
    },
)
async def get_reactions(
    ctx: Context,
    video_id: Annotated[str, "The Loom video ID"],
) -> str:
    """Get emoji reactions on a Loom video, including who reacted and at what timestamp."""
    client = _get_client(ctx)
    reactions = await _call(client.get_reactions(_id(video_id, "video ID")))
    if not reactions:
        return "No reactions on this video."
    lines = []
    for r in reactions:
        user = (r.get("user") or {}).get("display_name") or r.get(
            "anon_user_name", "Anonymous"
        )
        emoji = r.get("extended_reaction") or r.get("reaction", "")
        ts = f" @{r['time']}s" if r.get("time") is not None else ""
        lines.append(f"[{user}{ts}] {emoji}")
    return "\n".join(lines)


@mcp.tool(
    tags={"read"},
    timeout=30.0,
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
    },
)
async def get_meeting_notes(
    ctx: Context,
    video_id: Annotated[str, "The Loom video ID"],
) -> str:
    """Get the Confluence meeting notes URL linked to a Loom video."""
    client = _get_client(ctx)
    url = await _call(client.get_meeting_notes_url(_id(video_id, "video ID")))
    if not url:
        return "No meeting notes linked to this video."
    return url


@mcp.tool(
    tags={"read"},
    timeout=30.0,
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
    },
)
async def list_folders(
    ctx: Context,
    limit: Annotated[
        int, Field(description="Max folders to return (default 50)", ge=1, le=200)
    ] = 50,
) -> str:
    """List your Loom folders, sorted by most recent."""
    client = _get_client(ctx)
    folders = []
    cursor = None
    while len(folders) < limit:
        batch_size = min(50, limit - len(folders))
        result = await _call(client.list_folders(limit=batch_size, cursor=cursor))
        folders.extend(result["folders"])
        if not result["hasNextPage"]:
            break
        cursor = result["endCursor"]
    if not folders:
        return "No folders found."
    lines = [
        f"{f['id']}  {f['name']}  ({f.get('visibility', 'unknown')})" for f in folders
    ]
    return f"Found {len(folders)} folders:\n\n" + "\n".join(lines)


@mcp.tool(
    tags={"read"},
    timeout=30.0,
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
    },
)
async def list_spaces(ctx: Context) -> str:
    """List your Loom spaces (workspaces)."""
    client = _get_client(ctx)
    spaces = []
    cursor = None
    while True:
        result = await _call(client.list_spaces(limit=50, cursor=cursor))
        spaces.extend(result["spaces"])
        if not result["hasNextPage"]:
            break
        cursor = result["endCursor"]
    if not spaces:
        return "No spaces found."
    lines = []
    for s in spaces:
        primary = " (primary)" if s.get("is_primary") else ""
        privacy = s.get("privacy") or "unknown"
        lines.append(f"{s['id']}  {s['name']}  [{privacy}]{primary}")
    return f"Found {len(spaces)} spaces:\n\n" + "\n".join(lines)


@mcp.tool(
    tags={"read"},
    timeout=30.0,
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
    },
)
async def get_backlinks(
    ctx: Context,
    video_id: Annotated[str, "The Loom video ID"],
) -> str:
    """Get external references (backlinks) to a Loom video — where it's been shared or embedded."""
    client = _get_client(ctx)
    backlinks = await _call(client.get_backlinks(_id(video_id, "video ID")))
    if not backlinks:
        return "No backlinks for this video."
    lines = []
    for b in backlinks:
        source = b.get("source", "unknown")
        title = b.get("title", "Untitled")
        link = b.get("sourceLink", "")
        lines.append(f"[{source}] {title} — {link}")
    return "\n".join(lines)


@mcp.tool(
    tags={"read"},
    timeout=30.0,
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
    },
)
async def get_key_takeaways(
    ctx: Context,
    video_id: Annotated[str, "The Loom video ID"],
) -> str:
    """Get AI-generated key takeaways from a Loom video as a bullet list.

    For a narrative summary, use get_summary. For a detailed timestamped breakdown, use get_description.
    """
    client = _get_client(ctx)
    takeaways = await _call(client.get_key_takeaways(_id(video_id, "video ID")))
    if not takeaways:
        return "No key takeaways available for this video."
    return "\n".join(f"- {t}" for t in takeaways)


@mcp.tool(
    tags={"read"},
    timeout=30.0,
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
    },
)
async def get_tags(
    ctx: Context,
    video_id: Annotated[str, "The Loom video ID"],
) -> str:
    """Get tags on a Loom video."""
    client = _get_client(ctx)
    tags = await _call(client.get_tags(_id(video_id, "video ID")))
    if not tags:
        return "No tags on this video."
    return ", ".join(tags)


@mcp.tool(
    tags={"read"},
    timeout=30.0,
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
    },
)
async def get_description(
    ctx: Context,
    video_id: Annotated[str, "The Loom video ID"],
) -> str:
    """Get the AI-generated description of a Loom video with timestamped sections and bullet points.

    More detailed than get_summary. For a brief 1-2 sentence summary, use get_summary instead.
    """
    client = _get_client(ctx)
    desc = await _call(client.get_description(_id(video_id, "video ID")))
    if not desc:
        return "No description available for this video."
    return desc


@mcp.tool(
    tags={"read"},
    timeout=30.0,
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
    },
)
async def get_confluence_pages(
    ctx: Context,
    video_id: Annotated[str, "The Loom video ID"],
) -> str:
    """Get Confluence pages linked to a Loom video."""
    client = _get_client(ctx)
    pages = await _call(client.get_confluence_pages(_id(video_id, "video ID")))
    if not pages:
        return "No Confluence pages linked to this video."
    lines = [f"- [{p.get('title', 'Untitled')}]({p.get('url', '')})" for p in pages]
    return "\n".join(lines)


@mcp.tool(
    tags={"read"},
    timeout=30.0,
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
    },
)
async def search_folders(
    ctx: Context,
    query: Annotated[str, "Search query for folders"],
) -> str:
    """Search your Loom folders by name."""
    client = _get_client(ctx)
    folders = await _call(client.search_folders(query))
    if not folders:
        return f"No folders matching '{query}'"
    lines = [f"{f['id']}  {f['name']}" for f in folders]
    return f"Found {len(folders)} folders:\n\n" + "\n".join(lines)


@mcp.tool(
    tags={"read"},
    timeout=30.0,
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
    },
)
async def get_last_watch_time(
    ctx: Context,
    video_id: Annotated[str, "The Loom video ID"],
) -> str:
    """Get the last timestamp (in seconds) where you stopped watching a Loom video."""
    client = _get_client(ctx)
    time = await _call(client.get_last_watch_time(_id(video_id, "video ID")))
    if time is None:
        return "No watch history for this video."
    return f"Last watched at {time}s"


@mcp.tool(
    tags={"read"},
    timeout=30.0,
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
    },
)
async def get_watch_later_count(ctx: Context) -> str:
    """Get the number of videos in your Watch Later list."""
    client = _get_client(ctx)
    count = await _call(client.get_watch_later_count())
    return f"Watch Later list has {count} videos"


@mcp.tool(
    tags={"read"},
    timeout=30.0,
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
    },
)
async def get_total_videos_count(
    ctx: Context,
    user_id: Annotated[str, "The Loom user ID"],
) -> str:
    """Get the total number of videos created by a user."""
    client = _get_client(ctx)
    count = await _call(client.get_total_videos_count(_id(user_id, "user ID")))
    return f"User has {count} videos"


@mcp.tool(
    tags={"read"},
    timeout=30.0,
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
    },
)
async def get_frequent_reactions(ctx: Context) -> str:
    """Get your most frequently used emoji reaction types.

    Also useful to discover valid reaction type values for add_reaction.
    """
    client = _get_client(ctx)
    reactions = await _call(client.get_frequent_reactions())
    if not reactions:
        return "No recent reactions."
    return "Your frequent reactions: " + ", ".join(reactions)


@mcp.tool(
    tags={"read"},
    timeout=30.0,
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
    },
)
async def get_comment_reactions(
    ctx: Context,
    comment_id: Annotated[str, "The comment ID"],
    comment_type: Annotated[str, "Comment type: COMMENT or REPLY"] = "COMMENT",
) -> str:
    """Get emoji reactions on a specific comment."""
    client = _get_client(ctx)
    reactions = await _call(
        client.get_comment_reactions(_id(comment_id, "comment ID"), comment_type)
    )
    if not reactions:
        return "No reactions on this comment."
    lines = []
    for r in reactions:
        emoji = r.get("extendedReaction", "")
        user = r.get("userName", "Unknown")
        lines.append(f"[{user}] {emoji}")
    return "\n".join(lines)


@mcp.tool(
    tags={"read"},
    timeout=30.0,
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
    },
)
async def get_video_details(
    ctx: Context,
    video_id: Annotated[str, "The Loom video ID"],
) -> str:
    """Get all available information for a Loom video in one call: metadata, transcript, chapters, summary, tasks, and comments.

    Use this when you need a complete picture of a video. For just metadata, use get_video.
    """
    _id(video_id, "video ID")
    client = _get_client(ctx)
    video = await _call(client.get_video(video_id))
    if video.get("message"):
        raise ToolError(f"Cannot access video {video_id}: {video['message']}")
    transcript = await _call(client.get_transcript_text(video_id))
    chapters = await _call(client.get_chapters(video_id))
    summary = await _call(client.get_summary(video_id))
    comments = await _call(client.get_comments(video_id))
    tasks = await _call(client.get_tasks(video_id))

    parts = [f"# {video.get('name', 'Unknown')}\n"]

    duration = video.get("playable_duration", 0)
    m, s = divmod(int(duration), 60)
    h, m = divmod(m, 60)
    dur_str = f"{h}h {m}m {s}s" if h else f"{m}m {s}s"
    parts.append(f"**Duration:** {dur_str}")
    parts.append(f"**Created:** {video.get('createdAt', 'Unknown')}")
    parts.append(
        f"**Owner:** {(video.get('owner') or {}).get('display_name', 'Unknown')}"
    )
    parts.append(f"**Views:** {(video.get('views') or {}).get('total', 0)}")
    parts.append("")

    if chapters and chapters.get("content"):
        parts.append("## Chapters\n")
        parts.append(chapters["content"])
        parts.append("")

    if summary and summary.get("autoDescription"):
        parts.append("## AI Summary\n")
        parts.append(summary["autoDescription"])
        parts.append("")

    if transcript:
        parts.append("## Transcript\n")
        parts.append(transcript)
        parts.append("")

    if tasks:
        parts.append("## Action Items\n")
        for t in tasks:
            owner = (t.get("owner") or {}).get("display_name", "Unassigned")
            ts = f" @{t['time_stamp']}s" if t.get("time_stamp") is not None else ""
            status = "resolved" if t.get("resolved_at") else "open"
            parts.append(f"- [{status}] [{owner}{ts}] {t['content']}")
        parts.append("")

    if comments:
        parts.append("## Comments\n")
        for c in comments:
            ts = f" @{c['time_stamp']}s" if c.get("time_stamp") is not None else ""
            parts.append(f"- [{c['user_name']}{ts}] {c['content']}")
            for r in c.get("children_comments") or []:
                parts.append(f"  - [{r['user_name']}] {r['content']}")

    return "\n".join(parts)


@mcp.tool(
    tags={"read"},
    timeout=30.0,
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
    },
)
async def get_user(
    ctx: Context,
    user_id: Annotated[str, "The Loom user ID"],
) -> str:
    """Get a Loom user's profile by their ID — name, email, company, and avatar."""
    client = _get_client(ctx)
    user = await _call(client.get_user_by_id(_id(user_id, "user ID")))
    if not user:
        raise ToolError(f"User not found: {user_id}")
    return json.dumps(user, indent=2)


@mcp.tool(
    tags={"read"},
    timeout=30.0,
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
    },
)
async def search_workspace_tags(
    ctx: Context,
    query: Annotated[str, "Search query for tags"],
) -> str:
    """Search for tags in your Loom workspace."""
    client = _get_client(ctx)
    tags = await _call(client.search_workspace_tags(query))
    if not tags:
        return f"No tags matching '{query}'"
    return json.dumps(tags, indent=2)


@mcp.tool(
    tags={"read"},
    timeout=30.0,
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
    },
)
async def get_folder(
    ctx: Context,
    folder_id: Annotated[str, "The Loom folder ID"],
) -> str:
    """Get details of a Loom folder including name, visibility, and creator."""
    client = _get_client(ctx)
    folder = await _call(client.get_folder(_id(folder_id, "folder ID")))
    if not folder:
        raise ToolError(f"Folder not found: {folder_id}")
    return json.dumps(folder, indent=2)


# ---------------------------------------------------------------------------
# Write Tools
# ---------------------------------------------------------------------------


@mcp.tool(
    tags={"write"},
    timeout=30.0,
    annotations={
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": True,
    },
)
async def update_video_name(
    ctx: Context,
    video_id: Annotated[str, "The Loom video ID"],
    name: Annotated[str, "The new video name"],
) -> str:
    """Rename a Loom video. Overwrites the existing name."""
    client = _get_client(ctx)
    result = await _call(client.update_video_name(_id(video_id, "video ID"), name))
    return f"Renamed to: {result.get('name', name)}"


@mcp.tool(
    tags={"write"},
    timeout=30.0,
    annotations={
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": True,
    },
)
async def update_video_description(
    ctx: Context,
    video_id: Annotated[str, "The Loom video ID"],
    description: Annotated[str, "The new video description"],
) -> str:
    """Update the description of a Loom video. Overwrites the existing description."""
    client = _get_client(ctx)
    result = await _call(
        client.update_video_description(_id(video_id, "video ID"), description)
    )
    return json.dumps(result, indent=2)


@mcp.tool(
    tags={"write"},
    timeout=30.0,
    annotations={
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": True,
    },
)
async def update_video_settings(
    ctx: Context,
    video_id: Annotated[str, "The Loom video ID"],
    settings: Annotated[
        dict,
        'Settings to update (e.g. {"download_enabled": true, "comments_enabled": false})',
    ],
) -> str:
    """Update settings on a Loom video such as download_enabled, comments_enabled, etc."""
    client = _get_client(ctx)
    result = await _call(
        client.update_video_settings(_id(video_id, "video ID"), settings)
    )
    return json.dumps(result, indent=2)


@mcp.tool(
    tags={"write"},
    timeout=30.0,
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
    },
)
async def create_comment(
    ctx: Context,
    video_id: Annotated[str, "The Loom video ID"],
    content: Annotated[str, "The comment text"],
    timestamp: Annotated[
        int,
        Field(
            description="Timestamp in seconds to attach comment to (default 0)", ge=0
        ),
    ] = 0,
) -> str:
    """Post a comment on a Loom video. Each call creates a new comment."""
    client = _get_client(ctx)
    result = await _call(
        client.create_comment(_id(video_id, "video ID"), content, timestamp)
    )
    return json.dumps(result, indent=2)


@mcp.tool(
    tags={"write"},
    timeout=30.0,
    annotations={
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": True,
    },
)
async def edit_comment(
    ctx: Context,
    comment_id: Annotated[str, "The comment ID"],
    video_id: Annotated[str, "The Loom video ID the comment belongs to"],
    content: Annotated[str, "The new comment text"],
) -> str:
    """Edit an existing comment on a Loom video. Overwrites the comment text."""
    client = _get_client(ctx)
    result = await _call(
        client.edit_comment(
            _id(comment_id, "comment ID"), _id(video_id, "video ID"), content
        )
    )
    return json.dumps(result, indent=2)


@mcp.tool(
    tags={"write"},
    timeout=30.0,
    annotations={
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": True,
    },
)
async def delete_comment(
    ctx: Context,
    comment_id: Annotated[str, "The comment ID"],
) -> str:
    """Delete a comment from a Loom video. This cannot be undone."""
    client = _get_client(ctx)
    result = await _call(client.delete_comment(_id(comment_id, "comment ID")))
    return f"Comment deleted: {result}"


@mcp.tool(
    tags={"write"},
    timeout=30.0,
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
    },
)
async def create_task(
    ctx: Context,
    video_id: Annotated[str, "The Loom video ID"],
    content: Annotated[str, "The task/action item text"],
    timestamp: Annotated[
        int,
        Field(description="Timestamp in seconds to attach task to (default 0)", ge=0),
    ] = 0,
) -> str:
    """Create an action item (task) on a Loom video. Each call creates a new task."""
    client = _get_client(ctx)
    result = await _call(
        client.create_task(_id(video_id, "video ID"), content, timestamp)
    )
    return json.dumps(result, indent=2)


@mcp.tool(
    tags={"write"},
    timeout=30.0,
    annotations={
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": True,
    },
)
async def update_task(
    ctx: Context,
    task_id: Annotated[str, "The task ID"],
    content: Annotated[str, "The new task content"],
) -> str:
    """Update the content of an action item (task) on a Loom video."""
    client = _get_client(ctx)
    result = await _call(client.update_video_task(_id(task_id, "task ID"), content))
    return json.dumps(result, indent=2)


@mcp.tool(
    tags={"write"},
    timeout=30.0,
    annotations={
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": True,
    },
)
async def delete_task(
    ctx: Context,
    task_id: Annotated[str, "The task ID"],
) -> str:
    """Delete an action item (task) from a Loom video. This cannot be undone."""
    client = _get_client(ctx)
    result = await _call(client.delete_task(_id(task_id, "task ID")))
    return json.dumps(result, indent=2)


@mcp.tool(
    tags={"write"},
    timeout=30.0,
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
    },
)
async def approve_task(
    ctx: Context,
    task_id: Annotated[str, "The task ID"],
) -> str:
    """Mark an action item (task) as approved on a Loom video."""
    client = _get_client(ctx)
    result = await _call(client.approve_task(_id(task_id, "task ID")))
    return json.dumps(result, indent=2)


@mcp.tool(
    tags={"write"},
    timeout=30.0,
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
    },
)
async def respond_to_task(
    ctx: Context,
    task_id: Annotated[str, "The task ID"],
    responded: Annotated[bool, "True to mark as responded, False to unmark"] = True,
) -> str:
    """Respond to an action item (task) on a Loom video."""
    client = _get_client(ctx)
    result = await _call(client.respond_to_task(_id(task_id, "task ID"), responded))
    return json.dumps(result, indent=2)


@mcp.tool(
    tags={"write"},
    timeout=30.0,
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
    },
)
async def add_reaction(
    ctx: Context,
    video_id: Annotated[str, "The Loom video ID"],
    time: Annotated[
        int, Field(description="Timestamp in seconds for the reaction", ge=0)
    ],
    reaction_type: Annotated[
        str, "The reaction type — use get_frequent_reactions to see valid values"
    ],
) -> str:
    """Add an emoji reaction to a Loom video at a specific timestamp.

    Use get_frequent_reactions to discover valid reaction type values.
    """
    client = _get_client(ctx)
    result = await _call(
        client.add_reaction(_id(video_id, "video ID"), time, reaction_type)
    )
    if result.get("message"):
        raise ToolError(f"Failed to add reaction: {result['message']}")
    return json.dumps(result, indent=2)


@mcp.tool(
    tags={"write"},
    timeout=30.0,
    annotations={
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": True,
    },
)
async def delete_reaction(
    ctx: Context,
    reaction_id: Annotated[str, "The reaction ID"],
) -> str:
    """Delete an emoji reaction from a Loom video."""
    client = _get_client(ctx)
    result = await _call(client.delete_reaction(_id(reaction_id, "reaction ID")))
    return f"Reaction deleted: {result}"


@mcp.tool(
    tags={"write"},
    timeout=30.0,
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
    },
)
async def toggle_following(
    ctx: Context,
    video_id: Annotated[str, "The Loom video ID"],
    follow: Annotated[bool, "True to follow, False to unfollow"],
) -> str:
    """Follow or unfollow a Loom video to get notifications."""
    client = _get_client(ctx)
    result = await _call(client.toggle_following(_id(video_id, "video ID"), follow))
    return json.dumps(result, indent=2)


@mcp.tool(
    tags={"write"},
    timeout=30.0,
    annotations={
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": True,
    },
)
async def delete_video(
    ctx: Context,
    video_id: Annotated[str, "The Loom video ID"],
) -> str:
    """Permanently delete a Loom video. This cannot be undone.

    To temporarily remove a video, use archive_videos instead. To recover a recently deleted video, use recover_video.
    """
    client = _get_client(ctx)
    result = await _call(client.delete_video(_id(video_id, "video ID")))
    return f"Video deleted: {result}"


@mcp.tool(
    tags={"write"},
    timeout=30.0,
    annotations={
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": True,
    },
)
async def archive_videos(
    ctx: Context,
    video_ids: Annotated[list[str], "List of Loom video IDs to archive"],
    archive: Annotated[bool, "True to archive, False to unarchive"] = True,
) -> str:
    """Archive or unarchive Loom videos. Archived videos are hidden but not deleted."""
    client = _get_client(ctx)
    result = await _call(client.archive_videos(_ids(video_ids, "video ID"), archive))
    return json.dumps(result, indent=2)


@mcp.tool(
    tags={"write"},
    timeout=30.0,
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
    },
)
async def duplicate_video(
    ctx: Context,
    video_id: Annotated[str, "The Loom video ID"],
) -> str:
    """Duplicate a Loom video. Creates a new copy each time."""
    client = _get_client(ctx)
    result = await _call(client.duplicate_video(_id(video_id, "video ID")))
    return json.dumps(result, indent=2)


@mcp.tool(
    tags={"write"},
    timeout=30.0,
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
    },
)
async def add_to_watch_later(
    ctx: Context,
    video_id: Annotated[str, "The Loom video ID"],
    minutes_from_utc: Annotated[
        int, "Timezone offset in minutes from UTC (default 0)"
    ] = 0,
) -> str:
    """Add a Loom video to your Watch Later list."""
    client = _get_client(ctx)
    result = await _call(
        client.add_to_watch_later(_id(video_id, "video ID"), minutes_from_utc)
    )
    return json.dumps(result, indent=2)


@mcp.tool(
    tags={"write"},
    timeout=30.0,
    annotations={
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": True,
    },
)
async def remove_from_watch_later(
    ctx: Context,
    video_id: Annotated[str, "The Loom video ID"],
) -> str:
    """Remove a Loom video from your Watch Later list."""
    client = _get_client(ctx)
    result = await _call(client.remove_from_watch_later(_id(video_id, "video ID")))
    return json.dumps(result, indent=2)


@mcp.tool(
    tags={"write"},
    timeout=30.0,
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
    },
)
async def create_folder(
    ctx: Context,
    name: Annotated[str, "The folder name"],
) -> str:
    """Create a new Loom folder. Each call creates a new folder."""
    client = _get_client(ctx)
    result = await _call(client.create_folder(name))
    return json.dumps(result, indent=2)


@mcp.tool(
    tags={"write"},
    timeout=30.0,
    annotations={
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": True,
    },
)
async def rename_folder(
    ctx: Context,
    folder_id: Annotated[str, "The Loom folder ID"],
    name: Annotated[str, "The new folder name"],
) -> str:
    """Rename a Loom folder."""
    client = _get_client(ctx)
    result = await _call(client.rename_folder(_id(folder_id, "folder ID"), name))
    return json.dumps(result, indent=2)


@mcp.tool(
    tags={"write"},
    timeout=30.0,
    annotations={
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": True,
    },
)
async def delete_folders(
    ctx: Context,
    folder_ids: Annotated[list[str], "List of Loom folder IDs to delete"],
) -> str:
    """Delete one or more Loom folders. This cannot be undone."""
    client = _get_client(ctx)
    result = await _call(client.delete_folders(_ids(folder_ids, "folder ID")))
    return json.dumps(result, indent=2)


@mcp.tool(
    tags={"write"},
    timeout=30.0,
    annotations={
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": True,
    },
)
async def move_videos(
    ctx: Context,
    video_ids: Annotated[list[str], "List of Loom video IDs to move"],
    folder_id: Annotated[str, "The destination folder ID"],
) -> str:
    """Move one or more Loom videos to a different folder."""
    client = _get_client(ctx)
    result = await _call(
        client.bulk_move_videos(
            _ids(video_ids, "video ID"), _id(folder_id, "folder ID")
        )
    )
    return json.dumps(result, indent=2)


@mcp.tool(
    tags={"write"},
    timeout=30.0,
    annotations={
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": True,
    },
)
async def move_folders(
    ctx: Context,
    folder_ids: Annotated[list[str], "List of Loom folder IDs to move"],
    destination_folder_id: Annotated[str, "The destination parent folder ID"],
) -> str:
    """Move one or more Loom folders into a different parent folder."""
    client = _get_client(ctx)
    result = await _call(
        client.bulk_move_folders(
            _ids(folder_ids, "folder ID"), _id(destination_folder_id, "folder ID")
        )
    )
    return json.dumps(result, indent=2)


@mcp.tool(
    tags={"write"},
    timeout=30.0,
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
    },
)
async def recover_video(
    ctx: Context,
    video_id: Annotated[str, "The Loom video ID"],
) -> str:
    """Recover a deleted Loom video from the trash."""
    client = _get_client(ctx)
    result = await _call(client.recover_video(_id(video_id, "video ID")))
    return json.dumps(result, indent=2)


@mcp.tool(
    tags={"write"},
    timeout=30.0,
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
    },
)
async def pin_video(
    ctx: Context,
    video_id: Annotated[str, "The Loom video ID"],
    pinned: Annotated[bool, "True to pin, False to unpin"] = True,
) -> str:
    """Pin or unpin a Loom video in your library."""
    client = _get_client(ctx)
    await _call(client.update_video_pin_status(_id(video_id, "video ID"), pinned))
    action = "Pinned" if pinned else "Unpinned"
    return f"{action} video {video_id}"


@mcp.tool(
    tags={"write"},
    timeout=30.0,
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
    },
)
async def add_comment_reaction(
    ctx: Context,
    comment_id: Annotated[str, "The comment GUID"],
    reaction: Annotated[str, "The reaction emoji string (e.g. 'heart', '+1', 'fire')"],
    comment_type: Annotated[str, "Comment type: COMMENT or REPLY"] = "COMMENT",
) -> str:
    """Add an emoji reaction to a comment on a Loom video."""
    client = _get_client(ctx)
    result = await _call(
        client.add_comment_reaction(
            _id(comment_id, "comment ID"), reaction, comment_type
        )
    )
    return json.dumps(result, indent=2)


@mcp.tool(
    tags={"write"},
    timeout=30.0,
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
    },
)
async def toggle_following_tag(
    ctx: Context,
    tag: Annotated[str, "The tag name to follow/unfollow"],
    follow: Annotated[bool, "True to follow, False to unfollow"],
) -> str:
    """Follow or unfollow a tag in your Loom workspace to get notifications."""
    client = _get_client(ctx)
    await _call(client.toggle_following_tag(tag, follow))
    action = "Following" if follow else "Unfollowed"
    return f"{action} tag '{tag}'"


@mcp.tool(
    tags={"write"},
    timeout=30.0,
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
    },
)
async def share_videos_to_spaces(
    ctx: Context,
    video_ids: Annotated[list[str], "List of Loom video IDs to share"],
    space_ids: Annotated[list[str], "List of Loom space IDs to share to"],
) -> str:
    """Share one or more Loom videos to one or more spaces."""
    client = _get_client(ctx)
    result = await _call(
        client.batch_share_videos_to_spaces(
            _ids(video_ids, "video ID"), _ids(space_ids, "space ID")
        )
    )
    return json.dumps(result, indent=2)


def main():
    mcp.run()


if __name__ == "__main__":
    main()
