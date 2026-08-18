#!/usr/bin/env python3
"""Generate a podcast RSS feed (with Podcasting 2.0 chapters) from episode folders.

Each episode folder under --episodes-dir must contain:
  metadata.md (parsed loosely for Series/Title/Genre/Keywords/Description)
  chapters.json (list of {"title": ..., "start_seconds": ...})
  a .mp3 file (the final tagged episode audio)
  a cover .png

Enclosure/image URLs point at files already uploaded to a Nextcloud public
share, addressed via its WebDAV endpoint:
  https://<host>/public.php/dav/files/<share_token>/<filename>
"""

import argparse
import json
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path
from xml.sax.saxutils import escape

SERIES_TITLE = "The Hidden Skeleton"
SERIES_DESCRIPTION = (
    "Explores the hidden structure of language and how modern AI models learn, "
    "reconstruct, and reason with that structure. Calm, curious, deeply explanatory."
)
SERIES_AUTHOR = "Perryn"
SERIES_LANGUAGE = "en-us"


def parse_metadata(md_path: Path):
    text = md_path.read_text(encoding="utf-8")

    def field(name):
        m = re.search(rf"\*\*{name}:\*\*\s*(.+)", text)
        return m.group(1).strip() if m else ""

    return {
        "title": field("Title"),
        "genre": field("Genre"),
        "description": field("Description"),
    }


def rfc822(dt: datetime) -> str:
    return dt.strftime("%a, %d %b %Y %H:%M:%S %z")


def build_feed(episodes_dir: Path, base_url: str, feed_url: str, out_path: Path):
    episode_dirs = sorted(p for p in episodes_dir.iterdir() if p.is_dir())
    items_xml = []
    mtn = timezone(timedelta(hours=-6))
    pub_base = datetime(2026, 8, 17, 12, 0, 0, tzinfo=mtn)

    for i, ep_dir in enumerate(episode_dirs):
        meta_path = ep_dir / "metadata.md"
        chapters_path = ep_dir / "chapters.json"
        mp3_files = list(ep_dir.glob("*_final.mp3"))
        cover_files = [p for p in ep_dir.glob("*cover*.png")]
        if not (meta_path.exists() and mp3_files and cover_files):
            continue

        meta = parse_metadata(meta_path)
        mp3_path = mp3_files[0]
        cover_path = cover_files[0]
        chapters = json.loads(chapters_path.read_text()) if chapters_path.exists() else []

        mp3_url = f"{base_url}/{mp3_path.name}"
        cover_url = f"{base_url}/{cover_path.name}"
        size_bytes = mp3_path.stat().st_size
        pub_date = pub_base - timedelta(days=(len(episode_dirs) - 1 - i) * 7)
        guid = f"hidden-skeleton-ep{i+1:02d}"

        chapters_json_url = ""
        if chapters:
            pc_chapters_path = ep_dir / "podcast_chapters.json"
            pc_chapters_path.write_text(json.dumps({
                "version": "1.2.0",
                "chapters": [
                    {"startTime": c["start_seconds"], "title": c["title"]} for c in chapters
                ],
            }, indent=2))
            chapters_json_url = f"{base_url}/{pc_chapters_path.name}"

        # duration from last chapter start isn't total length; probe via soundfile if available
        try:
            import soundfile as sf
            info = sf.info(str(mp3_path))
            duration_s = int(info.frames / info.samplerate)
        except Exception:
            duration_s = 0
        h, rem = divmod(duration_s, 3600)
        m, s = divmod(rem, 60)
        duration_str = f"{h:02d}:{m:02d}:{s:02d}"

        chapters_tag = (
            f'<podcast:chapters url="{escape(chapters_json_url)}" type="application/json+chapters"/>'
            if chapters_json_url else ""
        )

        items_xml.append(f"""
    <item>
      <title>{escape(meta['title'])}</title>
      <description>{escape(meta['description'])}</description>
      <itunes:summary>{escape(meta['description'])}</itunes:summary>
      <pubDate>{rfc822(pub_date)}</pubDate>
      <guid isPermaLink="false">{guid}</guid>
      <enclosure url="{escape(mp3_url)}" length="{size_bytes}" type="audio/mpeg"/>
      <itunes:image href="{escape(cover_url)}"/>
      <itunes:duration>{duration_str}</itunes:duration>
      <itunes:episode>{i+1}</itunes:episode>
      <itunes:explicit>false</itunes:explicit>
      {chapters_tag}
    </item>""")

    series_cover_url = f"{base_url}/{cover_files[0].name}" if episode_dirs else ""

    feed = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"
     xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd"
     xmlns:podcast="https://podcastindex.org/namespace/1.0"
     xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>{escape(SERIES_TITLE)}</title>
    <description>{escape(SERIES_DESCRIPTION)}</description>
    <link>{escape(feed_url)}</link>
    <atom:link href="{escape(feed_url)}" rel="self" type="application/rss+xml"/>
    <language>{SERIES_LANGUAGE}</language>
    <itunes:author>{escape(SERIES_AUTHOR)}</itunes:author>
    <itunes:explicit>false</itunes:explicit>
    <itunes:image href="{escape(series_cover_url)}"/>
    <itunes:category text="Education"/>
    <generator>castapod podcast agent</generator>
    {''.join(items_xml)}
  </channel>
</rss>
"""
    out_path.write_text(feed, encoding="utf-8")
    print(f"Wrote {out_path} ({len(episode_dirs)} episode(s))")
    return [ep_dir / "podcast_chapters.json" for ep_dir in episode_dirs if (ep_dir / "chapters.json").exists()]


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--episodes-dir", required=True, type=Path)
    parser.add_argument("--base-url", required=True, help="Public URL prefix files are uploaded under")
    parser.add_argument("--feed-url", required=True, help="Public URL the feed itself will be served from")
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    build_feed(args.episodes_dir, args.base_url, args.feed_url, args.out)
