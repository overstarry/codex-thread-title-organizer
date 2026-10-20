---
name: setup-thread-title-organizer
description: Set up and diagnose the local Codex Thread Title Organizer plugin, including TypeSafe Jev credentials and hook trust.
---

# Set Up Thread Title Organizer

Configure this desktop-only plugin without exposing credentials or modifying unrelated Codex settings.

## Setup

1. Confirm that `pwsh` is available.
2. Confirm that `TYPESAFE_API_KEY` is set in the environment inherited by the Codex desktop app. Never print or persist its value.
3. Confirm that Codex hooks are enabled.
4. Ask the user to review and trust this plugin's hooks in the Codex hook UI. Do not bypass hook trust.
5. Start a fresh local Codex chat and complete one turn. Verify that the title receives exactly one known prefix.

The optional `TYPESAFE_MODEL` environment variable overrides the default `jev-latest` model.

## Diagnose

Run `scripts/test-contract.ps1` first. Run `scripts/test-live.ps1` only when the user expects a live TypeSafe API request and `TYPESAFE_API_KEY` is available.

Plugin runtime state is stored under `PLUGIN_DATA/sessions`. Do not inspect or expose stored prompt text unless the user explicitly asks for debugging that content.

If classification is uncertain, the plugin intentionally keeps the current title. If a rename continuation cannot access native Codex thread tools, report that integration boundary instead of editing Codex databases or transcript files.
