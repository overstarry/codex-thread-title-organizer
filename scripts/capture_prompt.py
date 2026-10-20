import json
import os
import sys
from datetime import datetime, timezone

from common import (
    read_session_state,
    session_state_path,
    write_hook_diagnostic,
    write_session_state,
)


def main():
    try:
        hook_input = json.loads(sys.stdin.read())
        session_id = str(hook_input.get("session_id", ""))
        prompt = str(hook_input.get("prompt", ""))
        if not session_id.strip() or not prompt.strip():
            return 0

        if prompt.startswith("[thread-title-organizer]"):
            return 0

        plugin_data = os.environ.get("PLUGIN_DATA", "")
        if not plugin_data.strip():
            raise RuntimeError("PLUGIN_DATA is not set.")

        state_path = session_state_path(plugin_data, session_id)
        state = read_session_state(state_path)
        state["session_id"] = session_id
        state["prompt"] = prompt
        state["captured_at"] = datetime.now(timezone.utc).isoformat()
        for key in (
            "last_requested_label",
            "last_requested_prefix",
            "last_confidence",
            "last_decision_source",
        ):
            state.pop(key, None)
        write_session_state(state_path, state)
    except Exception as error:
        write_hook_diagnostic(str(error))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
