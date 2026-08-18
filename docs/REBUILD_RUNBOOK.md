# Rebuild runbook (for an AI agent)

Purpose: if you're an AI agent asked to build this same kind of system — an autonomous podcast
production pipeline on local infrastructure — this is the order to do it in and the specific
dead ends to skip. Every gotcha here cost real time to discover the first time; don't
re-discover them.

Read `OVERVIEW.md` first for the shape of the finished thing. This doc is the "how," in build
order.

## 0. Survey before assuming

Don't trust a verbal description of "what's running" — verify with `ps aux`, `docker ps`,
`lsof -iTCP -sTCP:LISTEN`, and by reading actual config files. In the original build, the
user's description of the environment ("n8n, LM Studio, OpenClaw all running locally") was
correct, but several specific claims later turned out false on inspection: a "TTS model" in the
agent's config was actually a text LLM with a misleading name; a Matrix room the config claimed
to auto-join was never actually valid; a Nextcloud sync folder didn't exist yet. Verify, don't
assume, at every step where you're about to build on top of an existing piece of config.

## 1. TTS: get a real local voice working

This is the highest-risk piece — budget real time for it, and expect the "obvious" first
attempt to fail for non-obvious reasons.

1. Check whether **LM Studio** can serve the TTS model directly. It probably can't — LM Studio's
   runtime (as of this build) only supports chat/vision text-generation architectures, not
   TTS/audio-output architectures, even if the model shows up in its model list. Don't spend
   time debugging LM Studio config for this; move on immediately once you see an error like
   `Model type X not supported`.
2. Use **mlx-audio** instead (Apple Silicon only). Two gotchas:
   - The **PyPI release may lag the model you need**. If `pip show mlx-audio` succeeds but
     loading still fails with the same "not supported" error, check whether the architecture's
     module exists in the installed package (e.g.
     `python3 -c "import mlx_audio.tts.models.<arch_name>"`). If it's missing, install straight
     from GitHub main: `pip install git+https://github.com/Blaizzy/mlx-audio.git`.
   - mlx-audio requires **Python ≥3.10**. macOS's system `python3` (from Xcode Command Line
     Tools) is often 3.9.x, which silently breaks `pip install` from a git URL — instead of
     erring clearly, an old pip/setuptools combination can produce a bogus `UNKNOWN-0.0.0`
     package with the real code missing. If a package installs but the module still doesn't
     import, suspect the Python version before anything else. Fix: create a venv with a newer
     Homebrew Python (e.g. `/opt/homebrew/bin/python3.11 -m venv .venv`) and install there.
3. **A checkpoint downloaded by a different tool (e.g. LM Studio's own downloader) may be
   incomplete.** If loading fails with something like "Speech tokenizer not loaded" or a
   missing sub-component, check whether the model's HuggingFace repo has a nested subfolder
   (e.g. `speech_tokenizer/`) that the other tool's downloader skipped. Don't patch the
   incomplete local copy — just load by HF repo id (e.g.
   `mlx_audio.tts.utils.load("org/Model-Name")`) and let mlx-audio's own downloader pull the
   complete thing into its own HF cache.
4. Once loading works, generate a real test clip and **actually listen to it** (or have the
   user listen) before building anything on top of it. Don't assume "it ran without error" means
   "it sounds acceptable."

## 2. Voice pacing: prompt wording matters more than parameters

If the model takes an `instruct`/style-description parameter, watch out for a specific trap:
words like "calm" or "relaxed" in a pacing instruction can push generation toward *slow and
slurred*, not *natural*. What you actually want — natural pace, words clearly separated, not
rushed — needs to be spelled out that way explicitly, and calling it "calm" is not the same
thing. If a first take sounds sluggish/impaired rather than natural, suspect the instruct
wording before suspecting the model.

If the architecture supports multiple voice modes (e.g. a fixed small roster of preset
speakers vs. a "describe any voice in text" mode), the describe-any-voice mode is the practical
way to give different podcast series genuinely different voices without extra infrastructure —
much less work than voice cloning from reference audio.

## 3. QA loop: whisper transcribe-back

- Install `whisper.cpp` (e.g. `brew install whisper-cpp`) — it does **not** ship a model file by
  default; download one (e.g. `ggml-small.en.bin` from the ggerganov/whisper.cpp HF repo).
- QA method: transcribe the finished audio, diff the transcript against the source script,
  flag any transcript word that doesn't appear in the script.
- **Tokenization gotcha**: normalize both texts before comparing. Two specific traps found in
  practice:
  - `and`/`in` confusion at reduced/fast speech is common ASR noise, not a real error — a
    length filter (e.g. only flag words > 5 characters) filters most of this out for free.
  - **Hyphenated compounds transcribe unpredictably** — the same TTS engine produced
    "multi-dimensional" as one merged word ("multidimensional") in one case and
    "surface-level" as two separate words ("surface", "level") in another. Don't just strip or
    split hyphens one way; build **both** variants (merged and split) into the script's word set
    so either transcription outcome matches.
- Retry policy that held up in practice: **retry once with the same text** (catches
  stochastic sampling noise), and if the same word is flagged again, that's a real, consistent
  weak spot in the model — retrying further with identical text won't fix it. Reword the
  script around the flagged word instead (the fix that actually worked, twice, for two
  different words). Keep a running list of words this specific model mangles and bake it into
  every future script-drafting prompt as an explicit avoid-list.

## 4. Cover art

If the agent framework has (or can be given) a generic image-generation capability wired to a
cloud provider, use that rather than standing up local diffusion — it's a supporting feature,
not core to the build, and local diffusion is a real side-project on its own (worth deferring
unless explicitly asked for). Prompt for the visual style you want and explicitly rule out
clichés (e.g. "no glowing brains, no sci-fi motifs" for a tech/language topic) — models default
to the most stereotypical option otherwise.

## 5. Agent-framework config gotchas (OpenClaw-specific, but the pattern generalizes)

If the agent framework has a chat-channel bot account already configured:

- **Don't trust a channel/room reference in config until you've verified it resolves.** A room
  "allowlist" entry that's just a bare name (not a full room ID/alias) can sit in config
  looking valid while silently never actually working — the framework may log a warning (e.g.
  "rooms unresolved: X") that's easy to miss. Check the logs after any channel-related config
  change, and verify by actually sending a message and confirming delivery, not just by the
  config passing schema validation.
- If there's a lookup/resolve command in the framework's CLI (e.g. resolving a room name to
  its real ID), use it rather than guessing the exact ID format.
- **A config key existing doesn't mean the feature is active.** Plugins/capabilities can require
  an explicit enable step separate from configuring their settings — check the framework's
  plugin/capability listing, not just its config file, before assuming something is live.
- Prefer whatever the framework's built-in secret-storage mechanism is (e.g. an "auth
  paste-api-key" style command, or a ref-to-env-var pattern) over hand-editing plaintext
  secrets into a JSON config file, even if you find existing plaintext secrets already there as
  a bad-precedent pattern to *not* repeat.
- **Config changes to a running service usually need a restart to take effect** — but a restart
  mid-request will kill any in-flight work. Check nothing is actively running before restarting.

## 6. Local file storage / cloud sync gotchas (Nextcloud-specific, but the pattern generalizes)

- A modern desktop sync client (using the OS's virtual-filesystem integration, e.g. macOS
  FileProvider / CloudStorage) can have asymmetric permissions from a sandboxed shell: **reads
  can be blocked** ("Operation not permitted" on `ls`/`find`/`cat` into the mounted folder even
  though the folder demonstrably has content) **while writes work fine**, or vice versa — don't
  assume "read failed" means "folder is empty" or "sync is broken." Test both directions
  independently. The read block is typically a macOS Full Disk Access permission the running
  shell process lacks; writing new files/folders as that same process can still work because
  newly-created items get implicit access.
- There is generally no built-in "turn a folder into a podcast RSS feed" feature in a generic
  file-sync platform. Don't spend time hunting for one — build a small feed generator instead.
- The practical way to get stable public URLs for files in a private cloud-storage account
  without extra infrastructure: create one public share link for the target folder, then use the
  platform's direct-file-download URL pattern (for Nextcloud specifically:
  `https://<host>/public.php/dav/files/<share_token>/<filename>`) for both the audio files and
  the feed XML itself. Verify with `curl -I` that: (a) the content-type is right, (b) file sizes
  match, and (c) **HTTP Range requests work via GET** (`curl -H "Range: bytes=0-99"`) since
  podcast apps need this for streaming/seeking — a HEAD+Range combo may 500 even when GET+Range
  works fine; test with GET, not HEAD.
- The feed may get served with a generic content-type (e.g. `text/plain` instead of
  `application/rss+xml`) if the storage platform doesn't have an XML MIME mapping configured for
  public downloads. Most podcast apps tolerate this since they parse content regardless of the
  header, but it's worth flagging as a known risk rather than silently assuming it's fine.

## 7. Feed generation

Build a standard RSS 2.0 + iTunes-namespace feed generator. Key elements: `<enclosure>` with
correct `url`/`length`/`type`, `<itunes:image>`, `<itunes:duration>`, and if you want chapter
markers in modern podcast apps, the Podcasting 2.0 `<podcast:chapters>` tag pointing at a
separate small JSON file (format: `{"version": "1.2.0", "chapters": [{"startTime": N, "title":
"..."}]}`) rather than embedding chapters in the audio file's own tags — this is both simpler to
generate and the modern standard.

**Filename discipline across a multi-episode, flat public folder**: if every episode's local
working directory names its cover art the same generic thing (e.g. `cover.png`), and you
publish all episodes into one shared flat folder, later episodes will silently overwrite
earlier ones' live assets. Name files uniquely per episode from the start (e.g.
`episode<N>_cover.png`) in the *local* working directory too, not just at publish time — that
way the feed generator's URL-from-filename logic stays correct without a special case, and
"local filename" and "published filename" never diverge.

## 8. Bridging a containerized orchestrator to host-only tools (n8n-specific, but the pattern generalizes)

Before building anything in an orchestration tool that runs in Docker, check whether it can
actually reach what you need it to reach:

```
docker exec <container> sh -c "wget -qO- --timeout=5 http://host.docker.internal:<port>/<path>"
```

If the orchestrator's container has no host volume mounts and no host networking (check its
compose file), it cannot run local binaries (Python/ffmpeg/local models) or see host-only mounts
(a synced cloud-storage folder) directly. The fix is a small local HTTP API server on the host
that wraps everything the orchestrator needs, reachable from the container via
`host.docker.internal:<port>` (this resolves correctly on Docker Desktop for macOS, including to
services bound to `127.0.0.1` on the host — verify this specifically before relying on it).

Put the actual **orchestration logic** (multi-step sequencing, bounded retries, conditional
branches) in that host-side server, in a real programming language you can unit-test with
`curl`, rather than in the orchestrator's own visual node graph — especially if you're not
certain of the orchestrator's exact current node-parameter schema. A minimal orchestrator
workflow (trigger → one or two HTTP calls) is far more reliable to get right on the first try
than a multi-node graph with conditional branches guessed from memory.

### Discovering the exact node schema instead of guessing

If you need to hand-author the orchestrator's native workflow definition (e.g. as JSON, to
import via CLI rather than click through a UI) and you're not fully certain of the current
version's exact parameter names: **find the tool's own installed source and read it**, rather
than guessing from training data (tools iterate their config schemas over time). For an n8n
container, for example:

```
docker exec <container> find / -iname "<NodeName>.node.js" -not -path "*.map"
docker exec <container> sh -c "grep -n 'someParamName' /path/to/found/file.js"
```

This gives ground truth for parameter names, default `typeVersion`, and option shapes, for the
exact version actually installed — much more reliable than remembered API shapes.

### Triggering a workflow programmatically

- The orchestrator's own "run one execution" CLI command may try to spin up a second internal
  instance and port-conflict with the one already running as a service — don't assume it's the
  right tool for triggering a *live* running instance.
- Adding a webhook trigger node (in addition to whatever manual/UI trigger exists) gives a
  simple, dependency-free way to fire the live workflow with a plain HTTP call — useful both for
  your own testing and as the mechanism an agent-framework's chat bot can call when a human asks
  for something sooner than the schedule.
- If the orchestrator distinguishes "imported/saved" from "published/active," and requires a
  restart to pick up published changes: **do not restart while a triggered execution is still
  in flight** — check first (e.g. is the process that triggered it still running; has its
  expected output appeared yet) or you'll kill mid-pipeline work.

## 9. Persistence

Anything meant to run continuously (the host-side bridge server, in this build) should be a
real OS-level service (e.g. a macOS LaunchAgent `plist` with `RunAtLoad`/`KeepAlive`), not a
process left running in a terminal/session. Two gotchas specific to LaunchAgents:

- They get a **minimal environment** — no inherited shell `PATH`. If the service shells out to
  CLI tools installed via a package manager (Homebrew, etc.), set `PATH` explicitly in the
  plist's `EnvironmentVariables`, or every subprocess call will fail with "command not found"
  even though the same code works fine when run manually from an interactive shell.
- After creating/editing the plist: `launchctl bootout gui/$(id -u)/<label>` then
  `launchctl bootstrap gui/$(id -u) <path-to-plist>` to reload it with the new definition.

## 10. Retry/escalation policy for the QA loop

Don't build an unbounded retry loop, and don't silently auto-publish something QA flagged.
The policy that worked: retry once; if it still fails, **stop and hand off to a human** via
whatever notification channel exists (chat message describing exactly what was flagged and
where the script file is), rather than looping indefinitely or publishing anyway. Some failures
are genuinely not self-healing by the automation — they need a human to edit the script — and
pretending otherwise just produces bad published output or a hung pipeline.

## 11. Order of operations, summarized

1. Get a locally-running TTS voice actually producing acceptable audio (this is the long pole —
   don't parallelize other work ahead of nailing this down).
2. Get a transcribe-back QA check working and prove it catches a real, injected error before
   trusting it.
3. Wire up image generation.
4. Fix any broken existing chat-channel config (verify rooms/auth actually work, don't trust
   what's in the config file).
5. Get publishing (files + feed) working and prove the resulting URLs are actually fetchable
   with correct headers and range support — from outside your own machine if possible (e.g. a
   phone) before considering it done.
6. Build the host-side orchestration server, with each pipeline stage as its own tested
   endpoint, before touching the container-based orchestrator at all.
7. Wire the orchestrator up last, as thin plumbing on top of the already-working server, and
   validate it by actually triggering it (not just importing it) before calling it done.
8. Make the server persistent (LaunchAgent or equivalent).
9. Add whatever human-triggerable "do it now" path fits the existing chat/agent surface, on top
   of the same trigger the schedule uses — don't build a second code path for it.
