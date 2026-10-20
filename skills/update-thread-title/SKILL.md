---
name: update-thread-title
description: Refresh the current Codex chat title prefix from conversation state, or recover when the automatic title hook could not apply a rename.
---

# Update Thread Title

Use native Codex thread tools only.

1. Inspect the current root thread title and recent conversation state.
2. Select one prefix using this priority: blocked, validate, done, work in progress, plan, then task-kind fallback.
3. Remove all known organizer prefixes from the beginning of the current title.
4. Prepend exactly one selected prefix and keep the remaining title text unchanged.
5. Update only the current root thread.

Known prefixes are `⏸`, `👀`, `✅`, `🚧`, `💡`, `🐛`, `💬`, `🎨`, `✨`, and `🛠️`.

Do not edit Codex databases, internal state files, or transcript files. If native thread tools are unavailable, explain that limitation and stop.
