import json
import os
import sys
from datetime import datetime, timezone

from common import (
    invoke_jev_classification,
    new_jev_request,
    new_rename_continuation,
    read_session_state,
    resolve_title_decision,
    session_state_path,
    write_hook_diagnostic,
    write_hook_json,
    write_session_state,
)


def main():
    try:
        hook_input = json.loads(sys.stdin.read())
        if bool(hook_input.get("stop_hook_active")):
            write_hook_json({"continue": True})
            return 0

        session_id = str(hook_input.get("session_id", ""))
        plugin_data = os.environ.get("PLUGIN_DATA", "")
        if not session_id.strip() or not plugin_data.strip():
            write_hook_json({"continue": True})
            return 0

        state_path = session_state_path(plugin_data, session_id)
        state = read_session_state(state_path)
        prompt = str(state.get("prompt", ""))
        if not prompt.strip():
            write_hook_json({"continue": True})
            return 0

        api_key = os.environ.get("TYPESAFE_API_KEY", "")
        if not api_key.strip():
            raise RuntimeError("TYPESAFE_API_KEY is not set.")

        model = os.environ.get("TYPESAFE_MODEL", "").strip() or "jev-latest"
        request_body = new_jev_request(
            user_prompt=prompt,
            assistant_message=str(hook_input.get("last_assistant_message", "")),
            model=model,
        )
        response = invoke_jev_classification(request_body, api_key)
        decision = resolve_title_decision(response)

        state["last_model"] = str(response.get("model", ""))
        state["last_classified_at"] = datetime.now(timezone.utc).isoformat()
        if decision is None:
            state["last_outcome"] = "no_change"
            write_session_state(state_path, state)
            write_hook_json({"continue": True})
            return 0

        if state.get("last_requested_label") == decision["label"]:
            state["last_outcome"] = "unchanged"
            write_session_state(state_path, state)
            write_hook_json({"continue": True})
            return 0

        state["last_requested_label"] = decision["label"]
        state["last_requested_prefix"] = decision["prefix"]
        state["last_confidence"] = decision["confidence"]
        state["last_decision_source"] = decision["source"]
        state["last_outcome"] = "rename_requested"
        write_session_state(state_path, state)

        reason = new_rename_continuation(
            session_id=session_id,
            prefix=decision["prefix"],
            label=decision["label"],
        )
        write_hook_json({"decision": "block", "reason": reason})
    except Exception as error:
        write_hook_diagnostic(str(error))
        write_hook_json({"continue": True})

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
