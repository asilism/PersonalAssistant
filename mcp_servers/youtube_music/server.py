#!/usr/bin/env python3
"""
YouTube Music MCP Server

Provides YouTube music search and playback capabilities via MCP protocol.
Supports searching for music, playing in browser, and audio-only playback.
"""

import subprocess
import webbrowser
from typing import Optional

from fastmcp import FastMCP

# Create FastMCP server
mcp = FastMCP("youtube-music")


def run_yt_dlp_search(query: str, max_results: int = 5) -> list[dict]:
    """Search YouTube using yt-dlp."""
    try:
        import json

        # Use yt-dlp to search YouTube
        cmd = [
            "yt-dlp",
            f"ytsearch{max_results}:{query}",
            "--dump-json",
            "--flat-playlist",
            "--no-download",
            "--quiet",
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode != 0:
            return []

        # Parse JSON lines
        videos = []
        for line in result.stdout.strip().split("\n"):
            if line:
                try:
                    video = json.loads(line)
                    videos.append({
                        "id": video.get("id"),
                        "title": video.get("title"),
                        "url": f"https://www.youtube.com/watch?v={video.get('id')}",
                        "duration": video.get("duration"),
                        "channel": video.get("channel") or video.get("uploader"),
                        "view_count": video.get("view_count"),
                    })
                except json.JSONDecodeError:
                    continue

        return videos
    except subprocess.TimeoutExpired:
        return []
    except FileNotFoundError:
        return []
    except Exception:
        return []


def get_audio_url(video_url: str) -> Optional[str]:
    """Get the audio stream URL for a YouTube video."""
    try:
        cmd = [
            "yt-dlp",
            "-f", "bestaudio",
            "-g",  # Get URL only
            "--no-download",
            "--quiet",
            video_url,
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
        return None
    except Exception:
        return None


@mcp.tool()
def search_music(query: str, max_results: int = 5) -> dict:
    """Search for music on YouTube.

    Args:
        query: Search query (song name, artist, etc.)
        max_results: Maximum number of results to return (1-20)

    Returns:
        List of matching videos with titles, URLs, and metadata.
    """
    max_results = max(1, min(max_results, 20))

    videos = run_yt_dlp_search(query, max_results)

    if not videos:
        return {
            "success": False,
            "error": "No results found or yt-dlp not available. Install with: pip install yt-dlp",
            "videos": [],
        }

    return {
        "success": True,
        "query": query,
        "count": len(videos),
        "videos": videos,
    }


@mcp.tool()
def play_in_browser(url: str) -> dict:
    """Open a YouTube video in the default web browser.

    Args:
        url: YouTube video URL to open

    Returns:
        Result of the operation.
    """
    if not url.startswith(("https://www.youtube.com/", "https://youtube.com/", "https://youtu.be/")):
        return {
            "success": False,
            "error": "Invalid YouTube URL",
        }

    try:
        webbrowser.open(url)
        return {
            "success": True,
            "message": f"Opened in browser: {url}",
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }


@mcp.tool()
def play_audio(url: str, player: str = "auto") -> dict:
    """Play audio from a YouTube video using a media player.

    Uses mpv or vlc to play audio-only stream (no video window).

    Args:
        url: YouTube video URL
        player: Media player to use ('mpv', 'vlc', or 'auto')

    Returns:
        Result of the playback operation.
    """
    if not url.startswith(("https://www.youtube.com/", "https://youtube.com/", "https://youtu.be/")):
        return {
            "success": False,
            "error": "Invalid YouTube URL",
        }

    # Try different players
    players_to_try = []
    if player == "auto":
        players_to_try = ["mpv", "vlc"]
    else:
        players_to_try = [player]

    for p in players_to_try:
        try:
            if p == "mpv":
                # mpv with yt-dlp integration
                cmd = [
                    "mpv",
                    "--no-video",  # Audio only
                    "--really-quiet",
                    url,
                ]
            elif p == "vlc":
                cmd = [
                    "vlc",
                    "--intf", "dummy",  # No GUI
                    "--no-video",
                    url,
                ]
            else:
                continue

            # Start player in background
            subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

            return {
                "success": True,
                "message": f"Playing audio with {p}",
                "player": p,
                "url": url,
            }
        except FileNotFoundError:
            continue
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }

    return {
        "success": False,
        "error": f"No suitable media player found. Please install mpv or vlc.",
    }


@mcp.tool()
def search_and_play(
    query: str,
    play_mode: str = "browser",
) -> dict:
    """Search for music and play the first result.

    Convenience function that combines search and playback.

    Args:
        query: Search query (song name, artist, etc.)
        play_mode: How to play ('browser' to open in browser, 'audio' for audio-only)

    Returns:
        Result including search and playback status.
    """
    # Search for videos
    search_result = search_music(query, max_results=1)

    if not search_result.get("success") or not search_result.get("videos"):
        return {
            "success": False,
            "error": "No results found for query",
            "query": query,
        }

    video = search_result["videos"][0]
    url = video["url"]

    # Play based on mode
    if play_mode == "audio":
        play_result = play_audio(url)
    else:
        play_result = play_in_browser(url)

    return {
        "success": play_result.get("success", False),
        "query": query,
        "video": video,
        "playback": play_result,
    }


@mcp.tool()
def stop_playback() -> dict:
    """Stop all audio playback by killing media player processes.

    Returns:
        Result of stopping playback.
    """
    stopped = []

    for player in ["mpv", "vlc"]:
        try:
            result = subprocess.run(
                ["pkill", "-f", player],
                capture_output=True,
            )
            if result.returncode == 0:
                stopped.append(player)
        except Exception:
            pass

    if stopped:
        return {
            "success": True,
            "message": f"Stopped playback: {', '.join(stopped)}",
            "players_stopped": stopped,
        }
    else:
        return {
            "success": True,
            "message": "No active players found",
            "players_stopped": [],
        }


@mcp.tool()
def get_video_info(url: str) -> dict:
    """Get detailed information about a YouTube video.

    Args:
        url: YouTube video URL

    Returns:
        Video metadata including title, duration, channel, etc.
    """
    if not url.startswith(("https://www.youtube.com/", "https://youtube.com/", "https://youtu.be/")):
        return {
            "success": False,
            "error": "Invalid YouTube URL",
        }

    try:
        import json

        cmd = [
            "yt-dlp",
            "--dump-json",
            "--no-download",
            "--quiet",
            url,
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode != 0:
            return {
                "success": False,
                "error": "Failed to get video info",
            }

        video = json.loads(result.stdout)

        return {
            "success": True,
            "video": {
                "id": video.get("id"),
                "title": video.get("title"),
                "description": video.get("description", "")[:500],  # Truncate
                "duration": video.get("duration"),
                "duration_string": video.get("duration_string"),
                "channel": video.get("channel"),
                "channel_url": video.get("channel_url"),
                "view_count": video.get("view_count"),
                "like_count": video.get("like_count"),
                "upload_date": video.get("upload_date"),
                "thumbnail": video.get("thumbnail"),
                "url": url,
            },
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Request timed out"}
    except Exception as e:
        return {"success": False, "error": str(e)}


if __name__ == "__main__":
    # Run as streamable-HTTP server on port 8011
    mcp.run(transport="streamable-http", host="0.0.0.0", port=8011)
