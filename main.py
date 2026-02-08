import json
import os
from typing import Annotated

from fastmcp import FastMCP
from pydantic import Field

from loom_client import LoomClient

AUTH_FILE = os.environ.get("LOOM_AUTH_FILE", os.path.join(os.path.dirname(__file__), "..", "auth.json"))

mcp = FastMCP("Loom", instructions="Access Loom videos, transcripts, summaries, and comments.")

_client: LoomClient | None = None


def get_client() -> LoomClient:
    global _client
    if _client is None:
        _client = LoomClient(AUTH_FILE)
    return _client


@mcp.tool
async def list_videos(
    limit: Annotated[int, Field(description="Max videos to return (default 50)", ge=1, le=200)] = 50,
) -> str:
    """List your Loom videos, sorted by most recent. Returns video IDs and names."""
    client = get_client()
    videos = []
    cursor = None
    while len(videos) < limit:
        batch_size = min(50, limit - len(videos))
        result = await client.list_videos(limit=batch_size, cursor=cursor)
        videos.extend(result["videos"])
        if not result["hasNextPage"]:
            break
        cursor = result["endCursor"]
    lines = [f"{v['id']}  {v['name']}" for v in videos]
    return f"Found {len(videos)} videos:\n\n" + "\n".join(lines)


@mcp.tool
async def search_videos(
    query: Annotated[str, "Search query — supports natural language / semantic search"],
) -> str:
    """Search your Loom videos using AI-powered semantic search. Understands natural language queries, not just keywords."""
    client = get_client()
    matches = await client.search_videos(query)
    if not matches:
        return f"No videos matching '{query}'"
    lines = [f"{v['id']}  {v['name']}" for v in matches]
    return f"Found {len(matches)} matching videos:\n\n" + "\n".join(lines)


@mcp.tool
async def get_video(
    video_id: Annotated[str, "The Loom video ID (32-char hex string)"],
) -> str:
    """Get metadata for a Loom video including name, duration, owner, views, and creation date."""
    client = get_client()
    video = await client.get_video(video_id)
    return json.dumps(video, indent=2)


@mcp.tool
async def get_transcript(
    video_id: Annotated[str, "The Loom video ID"],
) -> str:
    """Get the full transcript of a Loom video with timestamps and speaker names."""
    client = get_client()
    text = await client.get_transcript_text(video_id)
    if not text:
        return "No transcript available for this video."
    return text


@mcp.tool
async def get_captions(
    video_id: Annotated[str, "The Loom video ID"],
) -> str:
    """Get the WebVTT captions of a Loom video. Unlike the transcript, captions include both start and end timestamps for each cue, making them ideal for precise timing analysis."""
    client = get_client()
    vtt = await client.get_captions(video_id)
    if not vtt:
        return "No captions available for this video."
    return vtt


@mcp.tool
async def get_summary(
    video_id: Annotated[str, "The Loom video ID"],
) -> str:
    """Get the AI-generated summary of a Loom video."""
    client = get_client()
    summary = await client.get_summary(video_id)
    if not summary or not summary.get("autoDescription"):
        return "No AI summary available for this video."
    return summary["autoDescription"]


@mcp.tool
async def get_chapters(
    video_id: Annotated[str, "The Loom video ID"],
) -> str:
    """Get the AI-generated chapters of a Loom video."""
    client = get_client()
    chapters = await client.get_chapters(video_id)
    if not chapters or not chapters.get("content"):
        return "No chapters available for this video."
    return chapters["content"]


@mcp.tool
async def get_comments(
    video_id: Annotated[str, "The Loom video ID"],
) -> str:
    """Get comments on a Loom video."""
    client = get_client()
    comments = await client.get_comments(video_id)
    if not comments:
        return "No comments on this video."
    lines = []
    for c in comments:
        ts = f" @{c['time_stamp']}s" if c.get("time_stamp") is not None else ""
        lines.append(f"[{c['user_name']}{ts}] {c['content']}")
        for r in c.get("children_comments") or []:
            lines.append(f"  └─ [{r['user_name']}] {r['content']}")
    return "\n".join(lines)


@mcp.tool
async def get_download_url(
    video_id: Annotated[str, "The Loom video ID"],
) -> str:
    """Get a signed download URL for the MP4 file of a Loom video."""
    client = get_client()
    url = await client.get_download_url(video_id)
    if not url:
        return "No download URL available for this video."
    return url


@mcp.tool
async def get_tasks(
    video_id: Annotated[str, "The Loom video ID"],
) -> str:
    """Get AI-generated action items (tasks) from a Loom video."""
    client = get_client()
    tasks = await client.get_tasks(video_id)
    if not tasks:
        return "No tasks/action items for this video."
    lines = []
    for t in tasks:
        owner = (t.get("owner") or {}).get("display_name", "Unassigned")
        ts = f" @{t['time_stamp']}s" if t.get("time_stamp") is not None else ""
        status = "resolved" if t.get("resolved_at") else "open"
        lines.append(f"[{status}] [{owner}{ts}] {t['content']}")
    return "\n".join(lines)


@mcp.tool
async def get_reactions(
    video_id: Annotated[str, "The Loom video ID"],
) -> str:
    """Get emoji reactions on a Loom video."""
    client = get_client()
    reactions = await client.get_reactions(video_id)
    if not reactions:
        return "No reactions on this video."
    lines = []
    for r in reactions:
        user = (r.get("user") or {}).get("display_name") or r.get("anon_user_name", "Anonymous")
        emoji = r.get("extended_reaction") or r.get("reaction", "")
        ts = f" @{r['time']}s" if r.get("time") is not None else ""
        lines.append(f"[{user}{ts}] {emoji}")
    return "\n".join(lines)


@mcp.tool
async def get_meeting_notes(
    video_id: Annotated[str, "The Loom video ID"],
) -> str:
    """Get the Confluence meeting notes URL linked to a Loom video."""
    client = get_client()
    url = await client.get_meeting_notes_url(video_id)
    if not url:
        return "No meeting notes linked to this video."
    return url


@mcp.tool
async def list_folders(
    limit: Annotated[int, Field(description="Max folders to return (default 50)", ge=1, le=200)] = 50,
) -> str:
    """List your Loom folders."""
    client = get_client()
    folders = []
    cursor = None
    while len(folders) < limit:
        batch_size = min(50, limit - len(folders))
        result = await client.list_folders(limit=batch_size, cursor=cursor)
        folders.extend(result["folders"])
        if not result["hasNextPage"]:
            break
        cursor = result["endCursor"]
    if not folders:
        return "No folders found."
    lines = [f"{f['id']}  {f['name']}  ({f.get('visibility', 'unknown')})" for f in folders]
    return f"Found {len(folders)} folders:\n\n" + "\n".join(lines)


@mcp.tool
async def list_spaces() -> str:
    """List your Loom spaces (workspaces)."""
    client = get_client()
    spaces = []
    cursor = None
    while True:
        result = await client.list_spaces(limit=50, cursor=cursor)
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


@mcp.tool
async def get_backlinks(
    video_id: Annotated[str, "The Loom video ID"],
) -> str:
    """Get external references (backlinks) to a Loom video — where it's been shared or embedded."""
    client = get_client()
    backlinks = await client.get_backlinks(video_id)
    if not backlinks:
        return "No backlinks for this video."
    lines = []
    for b in backlinks:
        source = b.get("source", "unknown")
        title = b.get("title", "Untitled")
        link = b.get("sourceLink", "")
        lines.append(f"[{source}] {title} — {link}")
    return "\n".join(lines)


@mcp.tool
async def get_key_takeaways(
    video_id: Annotated[str, "The Loom video ID"],
) -> str:
    """Get AI-generated key takeaways from a Loom video."""
    client = get_client()
    takeaways = await client.get_key_takeaways(video_id)
    if not takeaways:
        return "No key takeaways available for this video."
    return "\n".join(f"- {t}" for t in takeaways)


@mcp.tool
async def get_tags(
    video_id: Annotated[str, "The Loom video ID"],
) -> str:
    """Get tags on a Loom video."""
    client = get_client()
    tags = await client.get_tags(video_id)
    if not tags:
        return "No tags on this video."
    return ", ".join(tags)


@mcp.tool
async def get_description(
    video_id: Annotated[str, "The Loom video ID"],
) -> str:
    """Get the AI-generated description of a Loom video. More detailed than the summary — includes timestamped sections with bullet points."""
    client = get_client()
    desc = await client.get_description(video_id)
    if not desc:
        return "No description available for this video."
    return desc


@mcp.tool
async def get_confluence_pages(
    video_id: Annotated[str, "The Loom video ID"],
) -> str:
    """Get Confluence pages linked to a Loom video."""
    client = get_client()
    pages = await client.get_confluence_pages(video_id)
    if not pages:
        return "No Confluence pages linked to this video."
    lines = [f"- [{p.get('title', 'Untitled')}]({p.get('url', '')})" for p in pages]
    return "\n".join(lines)


@mcp.tool
async def search_folders(
    query: Annotated[str, "Search query for folders"],
) -> str:
    """Search your Loom folders by name."""
    client = get_client()
    folders = await client.search_folders(query)
    if not folders:
        return f"No folders matching '{query}'"
    lines = [f"{f['id']}  {f['name']}" for f in folders]
    return f"Found {len(folders)} folders:\n\n" + "\n".join(lines)


@mcp.tool
async def update_video_name(
    video_id: Annotated[str, "The Loom video ID"],
    name: Annotated[str, "The new video name"],
) -> str:
    """Rename a Loom video."""
    client = get_client()
    result = await client.update_video_name(video_id, name)
    return f"Renamed to: {result.get('name', name)}"


@mcp.tool
async def create_comment(
    video_id: Annotated[str, "The Loom video ID"],
    content: Annotated[str, "The comment text"],
    timestamp: Annotated[int, Field(description="Timestamp in seconds to attach comment to (default 0)", ge=0)] = 0,
) -> str:
    """Post a comment on a Loom video."""
    client = get_client()
    result = await client.create_comment(video_id, content, timestamp)
    return json.dumps(result, indent=2)


@mcp.tool
async def edit_comment(
    comment_id: Annotated[str, "The comment ID"],
    video_id: Annotated[str, "The Loom video ID the comment belongs to"],
    content: Annotated[str, "The new comment text"],
) -> str:
    """Edit an existing comment on a Loom video."""
    client = get_client()
    result = await client.edit_comment(comment_id, video_id, content)
    return json.dumps(result, indent=2)


@mcp.tool
async def delete_comment(
    comment_id: Annotated[str, "The comment ID"],
) -> str:
    """Delete a comment from a Loom video."""
    client = get_client()
    result = await client.delete_comment(comment_id)
    return f"Comment deleted: {result}"


@mcp.tool
async def create_task(
    video_id: Annotated[str, "The Loom video ID"],
    content: Annotated[str, "The task/action item text"],
    timestamp: Annotated[int, Field(description="Timestamp in seconds to attach task to (default 0)", ge=0)] = 0,
) -> str:
    """Create an action item (task) on a Loom video."""
    client = get_client()
    result = await client.create_task(video_id, content, timestamp)
    return json.dumps(result, indent=2)


@mcp.tool
async def delete_task(
    task_id: Annotated[str, "The task ID"],
) -> str:
    """Delete an action item (task) from a Loom video."""
    client = get_client()
    result = await client.delete_task(task_id)
    return json.dumps(result, indent=2)


@mcp.tool
async def approve_task(
    task_id: Annotated[str, "The task ID"],
) -> str:
    """Mark an action item (task) as approved on a Loom video."""
    client = get_client()
    result = await client.approve_task(task_id)
    return json.dumps(result, indent=2)


@mcp.tool
async def respond_to_task(
    task_id: Annotated[str, "The task ID"],
    responded: Annotated[bool, "True to mark as responded, False to unmark"] = True,
) -> str:
    """Respond to an action item (task) on a Loom video."""
    client = get_client()
    result = await client.respond_to_task(task_id, responded)
    return json.dumps(result, indent=2)


@mcp.tool
async def add_reaction(
    video_id: Annotated[str, "The Loom video ID"],
    time: Annotated[int, Field(description="Timestamp in seconds for the reaction", ge=0)],
    reaction_type: Annotated[str, "The reaction type — valid values: heart, +1, fire, clap, raised_hands, eyes"],
) -> str:
    """Add an emoji reaction to a Loom video at a specific timestamp. Use get_frequent_reactions to see valid types."""
    client = get_client()
    result = await client.add_reaction(video_id, time, reaction_type)
    return json.dumps(result, indent=2)


@mcp.tool
async def delete_reaction(
    reaction_id: Annotated[str, "The reaction ID"],
) -> str:
    """Delete an emoji reaction from a Loom video."""
    client = get_client()
    result = await client.delete_reaction(reaction_id)
    return f"Reaction deleted: {result}"


@mcp.tool
async def toggle_following(
    video_id: Annotated[str, "The Loom video ID"],
    follow: Annotated[bool, "True to follow, False to unfollow"],
) -> str:
    """Follow or unfollow a Loom video to get notifications."""
    client = get_client()
    result = await client.toggle_following(video_id, follow)
    return json.dumps(result, indent=2)


@mcp.tool
async def delete_video(
    video_id: Annotated[str, "The Loom video ID"],
) -> str:
    """Permanently delete a Loom video."""
    client = get_client()
    result = await client.delete_video(video_id)
    return f"Video deleted: {result}"


@mcp.tool
async def archive_videos(
    video_ids: Annotated[list[str], "List of Loom video IDs to archive"],
    archive: Annotated[bool, "True to archive, False to unarchive"] = True,
) -> str:
    """Archive or unarchive Loom videos."""
    client = get_client()
    result = await client.archive_videos(video_ids, archive)
    return json.dumps(result, indent=2)


@mcp.tool
async def duplicate_video(
    video_id: Annotated[str, "The Loom video ID"],
) -> str:
    """Duplicate a Loom video."""
    client = get_client()
    result = await client.duplicate_video(video_id)
    return json.dumps(result, indent=2)


@mcp.tool
async def update_video_description(
    video_id: Annotated[str, "The Loom video ID"],
    description: Annotated[str, "The new video description"],
) -> str:
    """Update the description of a Loom video."""
    client = get_client()
    result = await client.update_video_description(video_id, description)
    return json.dumps(result, indent=2)


@mcp.tool
async def add_to_watch_later(
    video_id: Annotated[str, "The Loom video ID"],
    minutes_from_utc: Annotated[int, "Timezone offset in minutes from UTC (default 0)"] = 0,
) -> str:
    """Add a Loom video to your Watch Later list."""
    client = get_client()
    result = await client.add_to_watch_later(video_id, minutes_from_utc)
    return json.dumps(result, indent=2)


@mcp.tool
async def remove_from_watch_later(
    video_id: Annotated[str, "The Loom video ID"],
) -> str:
    """Remove a Loom video from your Watch Later list."""
    client = get_client()
    result = await client.remove_from_watch_later(video_id)
    return json.dumps(result, indent=2)


@mcp.tool
async def get_folder(
    folder_id: Annotated[str, "The Loom folder ID"],
) -> str:
    """Get details of a Loom folder."""
    client = get_client()
    folder = await client.get_folder(folder_id)
    if not folder:
        return "Folder not found."
    return json.dumps(folder, indent=2)


@mcp.tool
async def create_folder(
    name: Annotated[str, "The folder name"],
) -> str:
    """Create a new Loom folder."""
    client = get_client()
    result = await client.create_folder(name)
    return json.dumps(result, indent=2)


@mcp.tool
async def rename_folder(
    folder_id: Annotated[str, "The Loom folder ID"],
    name: Annotated[str, "The new folder name"],
) -> str:
    """Rename a Loom folder."""
    client = get_client()
    result = await client.rename_folder(folder_id, name)
    return json.dumps(result, indent=2)


@mcp.tool
async def delete_folders(
    folder_ids: Annotated[list[str], "List of Loom folder IDs to delete"],
) -> str:
    """Delete one or more Loom folders."""
    client = get_client()
    result = await client.delete_folders(folder_ids)
    return json.dumps(result, indent=2)


@mcp.tool
async def get_last_watch_time(
    video_id: Annotated[str, "The Loom video ID"],
) -> str:
    """Get the last timestamp (in seconds) where you stopped watching a Loom video."""
    client = get_client()
    time = await client.get_last_watch_time(video_id)
    if time is None:
        return "No watch history for this video."
    return f"Last watched at {time}s"


@mcp.tool
async def get_watch_later_count() -> str:
    """Get the number of videos in your Watch Later list."""
    client = get_client()
    count = await client.get_watch_later_count()
    return f"Watch Later list has {count} videos"


@mcp.tool
async def get_total_videos_count(
    user_id: Annotated[str, "The Loom user ID"],
) -> str:
    """Get the total number of videos created by a user."""
    client = get_client()
    count = await client.get_total_videos_count(user_id)
    return f"User has {count} videos"


@mcp.tool
async def get_frequent_reactions() -> str:
    """Get your most frequently used emoji reaction types. Also useful to discover valid reaction type values."""
    client = get_client()
    reactions = await client.get_frequent_reactions()
    if not reactions:
        return "No recent reactions."
    return "Your frequent reactions: " + ", ".join(reactions)


@mcp.tool
async def get_comment_reactions(
    comment_id: Annotated[str, "The comment ID"],
    comment_type: Annotated[str, "Comment type: COMMENT or REPLY"] = "COMMENT",
) -> str:
    """Get emoji reactions on a specific comment."""
    client = get_client()
    reactions = await client.get_comment_reactions(comment_id, comment_type)
    if not reactions:
        return "No reactions on this comment."
    lines = []
    for r in reactions:
        emoji = r.get("extendedReaction", "")
        user = r.get("userName", "Unknown")
        lines.append(f"[{user}] {emoji}")
    return "\n".join(lines)


@mcp.tool
async def get_video_details(
    video_id: Annotated[str, "The Loom video ID"],
) -> str:
    """Get all available information for a Loom video: metadata, transcript, chapters, summary, and comments."""
    client = get_client()
    video = await client.get_video(video_id)
    transcript = await client.get_transcript_text(video_id)
    chapters = await client.get_chapters(video_id)
    summary = await client.get_summary(video_id)
    comments = await client.get_comments(video_id)
    tasks = await client.get_tasks(video_id)

    parts = [f"# {video.get('name', 'Unknown')}\n"]

    duration = video.get("playable_duration", 0)
    m, s = divmod(int(duration), 60)
    h, m = divmod(m, 60)
    dur_str = f"{h}h {m}m {s}s" if h else f"{m}m {s}s"
    parts.append(f"**Duration:** {dur_str}")
    parts.append(f"**Created:** {video.get('createdAt', 'Unknown')}")
    parts.append(f"**Owner:** {(video.get('owner') or {}).get('display_name', 'Unknown')}")
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


@mcp.tool
async def get_user(
    user_id: Annotated[str, "The Loom user ID"],
) -> str:
    """Get a Loom user's profile by their ID — name, email, company, and avatar."""
    client = get_client()
    user = await client.get_user_by_id(user_id)
    if not user:
        return "User not found."
    return json.dumps(user, indent=2)


@mcp.tool
async def search_workspace_tags(
    query: Annotated[str, "Search query for tags"],
) -> str:
    """Search for tags in your Loom workspace."""
    client = get_client()
    tags = await client.search_workspace_tags(query)
    if not tags:
        return f"No tags matching '{query}'"
    return json.dumps(tags, indent=2)


@mcp.tool
async def move_videos(
    video_ids: Annotated[list[str], "List of Loom video IDs to move"],
    folder_id: Annotated[str, "The destination folder ID"],
) -> str:
    """Move one or more Loom videos to a different folder."""
    client = get_client()
    result = await client.bulk_move_videos(video_ids, folder_id)
    return json.dumps(result, indent=2)


@mcp.tool
async def move_folders(
    folder_ids: Annotated[list[str], "List of Loom folder IDs to move"],
    destination_folder_id: Annotated[str, "The destination parent folder ID"],
) -> str:
    """Move one or more Loom folders into a different parent folder."""
    client = get_client()
    result = await client.bulk_move_folders(folder_ids, destination_folder_id)
    return json.dumps(result, indent=2)


@mcp.tool
async def recover_video(
    video_id: Annotated[str, "The Loom video ID"],
) -> str:
    """Recover a deleted Loom video from the trash."""
    client = get_client()
    result = await client.recover_video(video_id)
    return json.dumps(result, indent=2)


@mcp.tool
async def pin_video(
    video_id: Annotated[str, "The Loom video ID"],
    pinned: Annotated[bool, "True to pin, False to unpin"] = True,
) -> str:
    """Pin or unpin a Loom video in your library."""
    client = get_client()
    result = await client.update_video_pin_status(video_id, pinned)
    action = "Pinned" if pinned else "Unpinned"
    return f"{action} video {video_id}"


@mcp.tool
async def add_comment_reaction(
    comment_id: Annotated[str, "The comment GUID"],
    reaction: Annotated[str, "The reaction emoji string (e.g. 'heart', '+1', 'fire')"],
    comment_type: Annotated[str, "Comment type: COMMENT or REPLY"] = "COMMENT",
) -> str:
    """Add an emoji reaction to a comment on a Loom video."""
    client = get_client()
    result = await client.add_comment_reaction(comment_id, reaction, comment_type)
    return json.dumps(result, indent=2)


@mcp.tool
async def toggle_following_tag(
    tag: Annotated[str, "The tag name to follow/unfollow"],
    follow: Annotated[bool, "True to follow, False to unfollow"],
) -> str:
    """Follow or unfollow a tag in your Loom workspace to get notifications."""
    client = get_client()
    result = await client.toggle_following_tag(tag, follow)
    action = "Following" if follow else "Unfollowed"
    return f"{action} tag '{tag}'"


@mcp.tool
async def share_videos_to_spaces(
    video_ids: Annotated[list[str], "List of Loom video IDs to share"],
    space_ids: Annotated[list[str], "List of Loom space IDs to share to"],
) -> str:
    """Share one or more Loom videos to one or more spaces."""
    client = get_client()
    result = await client.batch_share_videos_to_spaces(video_ids, space_ids)
    return json.dumps(result, indent=2)


@mcp.tool
async def update_video_settings(
    video_id: Annotated[str, "The Loom video ID"],
    settings: Annotated[dict, "Settings to update (e.g. {\"download_enabled\": true, \"comments_enabled\": false})"],
) -> str:
    """Update settings on a Loom video such as download_enabled, comments_enabled, etc."""
    client = get_client()
    result = await client.update_video_settings(video_id, settings)
    return json.dumps(result, indent=2)


@mcp.tool
async def update_task(
    task_id: Annotated[str, "The task ID"],
    content: Annotated[str, "The new task content"],
) -> str:
    """Update the content of an action item (task) on a Loom video."""
    client = get_client()
    result = await client.update_video_task(task_id, content)
    return json.dumps(result, indent=2)


if __name__ == "__main__":
    mcp.run()
