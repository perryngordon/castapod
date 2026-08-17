# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project status

This repository is in the pre-implementation planning stage. It currently contains no source code, build system, or tests — only a design conversation at `thinking/initial-prompt.md` describing the intended project.

There are no build, lint, or test commands yet because no code exists. Do not invent tooling or assume a stack until it is actually introduced in the repo.

## Project intent

The goal (from `thinking/initial-prompt.md`) is a podcast agent that continuously builds a library of AI-generated podcasts into a Nextcloud podcast folder:

- Generates episodes with high-quality TTS (no speech artifacts).
- Generates cover art and embeds it directly into the audio files.
- Maintains a "Chapter 0" episode/file holding series cover art, intro, metadata, and a style guide that the agent updates over time.
- Watches the Nextcloud folder and publishes finished episodes there.
- Requests human guidance/feedback on podcast direction via Element (Matrix client), and iterates based on it.
- Runs a QA loop over generated audio (pronunciation, pacing, emphasis) before publishing.

Sketched architecture (not yet built): Nextcloud sync on a Mac mini, n8n as the automation engine, an agent runtime ("OpenClaw") as the agent brain, LM Studio for local LLMs, an MCP server exposing local tools (ffmpeg, whisper, filesystem), and Element for the human feedback loop.

When implementation begins, update this file with real commands and architecture derived from the actual code — do not keep speculative details here once they're superseded by working code.
