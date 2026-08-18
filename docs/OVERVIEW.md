# Castapod — The Hidden Skeleton podcast agent

An autonomous system that researches, writes, narrates, illustrates, QA-checks, and publishes
podcast episodes on its own, running entirely on local infrastructure (one Mac mini-class
machine), with a human feedback loop over Matrix/Element.

The pilot series, **"The Hidden Skeleton,"** teaches computational linguistics / NLP as a
13-episode course — see `~/.openclaw/workspace/podcast-agent/CHAPTER_0.md` on the production
machine for the curriculum, voice/style decisions, and episode-by-episode change log. This repo
holds the code; the "series bible" and produced episode assets live in the OpenClaw workspace
because that's what the agent actually reads before writing each episode.

## Why this exists

`thinking/initial-prompt.md` has the original pitch: generate tailored podcast episodes with
clean TTS and baked-in cover art, keep a "Chapter 0" style guide the agent maintains itself, QA
audio before publishing, and ask for human guidance over chat rather than gating every episode
on approval. Everything below is that idea, built and running.

## Architecture

```
                    ┌─────────────────────────┐
   every 6h  ──────▶│   n8n (Docker, :5678)   │◀────── webhook / manual trigger
   (cron)           │   orchestration only     │        (chat: "make the next episode now")
                    └────────────┬─────────────┘
                                 │ HTTP, via host.docker.internal
                                 ▼
                    ┌─────────────────────────────────────────┐
                    │  production_server.py (host, :8765)      │
                    │  LaunchAgent — does the actual work       │
                    └───┬─────┬─────┬─────┬─────┬─────┬────────┘
                        │     │     │     │     │     │
                 research│  script│  audio│    qa│ cover│  publish+notify
                        ▼     ▼     ▼     ▼     ▼     ▼
                    Brave   LM     mlx-  whisper OpenAI Nextcloud
                    search  Studio audio  .cpp   images  + Matrix
                    (via    (text  (TTS)                (feed +
                    OpenClaw) LLM)                       episode)
```

**n8n is fully containerized** (Docker Compose, no host volumes, no host networking) — it
cannot run mlx-audio, whisper.cpp, ffmpeg, or the OpenClaw CLI, and it can't see the Nextcloud
sync folder. All of those are host-only (several are macOS/Apple-Silicon-specific). So n8n's job
is reduced to *when* to run, not *how*: a trigger fires, it asks the host-side server what
episode is next, then asks it to produce that episode. All real work happens in
`scripts/production_server.py`, reachable from the container via `host.docker.internal:8765`.

## The pipeline, stage by stage

1. **Research** — `openclaw infer web search` (Brave, already configured in OpenClaw) pulls a
   handful of real sources for the episode's topic. This grounds the script in actual
   terminology and examples instead of whatever the local model half-remembers.
2. **Script** — LM Studio (`google/gemma-4-12b-qat`, a local reasoning model) drafts the full
   episode as markdown chapters, given the series bible (Chapter 0), the curriculum entry, and
   the research notes. Prompted explicitly for TTS-friendly prose and to avoid words the TTS
   engine is known to mangle.
3. **Audio** — `scripts/produce_episode.py` renders each chapter separately through
   **Qwen3-TTS-12Hz** (via `mlx-audio`, Apple Silicon-native) with a fixed voice/style, then
   concatenates them with natural gaps. Per-chapter rendering gives exact chapter-marker
   timestamps for free.
4. **QA** — `whisper.cpp` transcribes the finished audio back to text and diffs it against the
   script. A mismatch longer than a few characters gets flagged as a likely mispronunciation.
   One retry is attempted (same script, different TTS sampling); if it still fails, the episode
   is **not** published — instead a message goes to the Matrix room describing what got
   flagged, so a human can fix the script and re-trigger.
5. **Cover art** — OpenAI's image API (`gpt-image-1`), prompted for abstract branching-structure
   art matching the series' visual identity, no clichés (no glowing brains, no sci-fi).
6. **Finalize** — `ffmpeg` embeds the cover art and ID3 metadata (title, series, chapter
   markers) into the final MP3.
7. **Publish** — the episode and its assets are copied into a Nextcloud-synced folder (which is
   also a public share), and `scripts/generate_feed.py` regenerates a standards-compliant
   podcast RSS 2.0 feed (with Podcasting 2.0 `<podcast:chapters>`) referencing the public share's
   direct-download URLs. Nextcloud has no built-in "folder to podcast feed" feature, so this is
   hand-rolled.
8. **Notify** — a Matrix message announces the new episode (or the QA escalation), through
   OpenClaw's existing bot account.

## How production gets triggered

Three ways, all hitting the same n8n webhook (`GET
http://localhost:5678/webhook/produce-next-episode`), which finds whatever the next unproduced
curriculum episode is and runs the whole pipeline on it:

- **Cron** — every 6 hours, via an n8n Schedule Trigger node.
- **Chat** — ask the OpenClaw assistant in the Matrix room for a new episode sooner; it's been
  told (see `~/.openclaw/workspace/TOOLS.md`) to hit the webhook itself.
- **Manual** — the n8n UI's "Execute Workflow" button, for testing.

## Key decisions and why

| Decision | Reasoning |
|---|---|
| Qwen3-TTS-12Hz via mlx-audio, not a cloud TTS API | Fully local, no per-episode cost, Apple Silicon-native. Required building the mlx-audio serving path from scratch (see the rebuild runbook). |
| OpenAI for cover art, not local diffusion | Cover art is a supporting feature, not the hard part of this build — a cloud API unblocks it in one afternoon; local diffusion is its own project, deferred. |
| Real RSS feed, not a plain synced folder | The user wanted genuine offline listening in a normal podcast app (subscribe → download → play), which requires an actual feed, not just files sitting in a folder. |
| Orchestration logic lives in Python (`production_server.py`), not n8n node wiring | n8n's exact node JSON schema for this version wasn't something to guess blind, and a Python HTTP server is directly testable with `curl`. n8n's role is deliberately thin: trigger, and one HTTP call. |
| QA retries once, then escalates instead of looping or auto-publishing a flagged episode | Two real failures during development were consistent model weaknesses (not random noise) that a same-text retry never fixed — only a script reword did. So the policy assumes a human edit is sometimes genuinely required, and hands off cleanly instead of pretending automation can always self-heal. |

## Where things live

- `scripts/` — all pipeline code (this repo).
- `~/.openclaw/workspace/podcast-agent/CHAPTER_0.md` — series bible: identity, goal, curriculum,
  voice/pacing decisions, known TTS pronunciation gotchas, change log.
- `~/.openclaw/workspace/podcast-agent/episodes/epNN/` — per-episode script, research notes,
  chapter timestamps, cover art, final audio.
- `~/.openclaw/workspace/TOOLS.md` — the chat-trigger instruction for the assistant.
- Nextcloud `podcasts/public/` (public share) — the live, published feed and audio files.
- `~/Library/LaunchAgents/com.castapod.production-server.plist` — keeps the production API
  server running persistently.
