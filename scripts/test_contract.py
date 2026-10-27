import io
import json
import os
import subprocess
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path

import capture_prompt
import classify_title
from common import (
    new_jev_request,
    new_rename_continuation,
    resolve_title_decision,
)


SCRIPT_DIRECTORY = Path(__file__).resolve().parent


def assert_equal(expected, actual, message):
    if expected != actual:
        raise AssertionError(f"{message} Expected {expected!r}, got {actual!r}.")


def test_decision_policy():
    changed_response = {
        "answers": {
            "desired_label": {"choice": "blocked", "confidence": 0.93},
        }
    }
    changed_decision = resolve_title_decision(changed_response)
    assert_equal("blocked", changed_decision["label"], "Changed label mismatch.")
    assert_equal("⏸", changed_decision["prefix"], "Blocked prefix mismatch.")

    moderate_response = {
        "answers": {
            "desired_label": {"choice": "chat", "confidence": 0.55},
        }
    }
    assert_equal(
        "chat",
        resolve_title_decision(moderate_response)["label"],
        "A moderate-confidence title decision must remain actionable.",
    )

    uncertain_response = {
        "answers": {
            "desired_label": {"choice": "chat", "confidence": 0.31},
        }
    }
    assert_equal(
        None,
        resolve_title_decision(uncertain_response),
        "Uncertain decisions must not rename.",
    )


def test_request_and_continuation_contract():
    continuation = new_rename_continuation("thread-123", "✅", "done")
    if not continuation.startswith("[thread-title-organizer]"):
        raise AssertionError("Continuation marker is missing.")
    if "Do not modify any other thread" not in continuation:
        raise AssertionError("Continuation scope guard is missing.")

    request = new_jev_request(
        "Implement the feature.",
        "Implementation is complete.",
    )
    assert_equal("jev-latest", request["model"], "Default model mismatch.")
    if "previous_label" in request["state"]:
        raise AssertionError("Jev must classify absolute state without label anchoring.")
    assert_equal(1, len(request["questions"]), "Jev must use one label choice.")
    criteria = request["questions"]["desired_label"]["criteria"]
    if "keep" in criteria:
        raise AssertionError("An absolute title classification must not allow keep.")


def test_hook_subprocess_contract():
    with tempfile.TemporaryDirectory() as plugin_data:
        environment = os.environ.copy()
        environment["PLUGIN_DATA"] = plugin_data

        capture_result = subprocess.run(
            [sys.executable, str(SCRIPT_DIRECTORY / "capture_prompt.py")],
            input=json.dumps(
                {
                    "session_id": "contract/session",
                    "prompt": "Investigate a failing webhook retry",
                }
            ),
            text=True,
            capture_output=True,
            check=False,
            env=environment,
        )
        assert_equal(0, capture_result.returncode, "Capture hook must exit cleanly.")
        state_path = Path(plugin_data) / "sessions" / "contract_session.json"
        if not state_path.is_file():
            raise AssertionError("Capture hook did not create session state.")

        stop_result = subprocess.run(
            [sys.executable, str(SCRIPT_DIRECTORY / "classify_title.py")],
            input=json.dumps(
                {
                    "session_id": "contract/session",
                    "stop_hook_active": True,
                    "last_assistant_message": "Done",
                }
            ),
            text=True,
            capture_output=True,
            check=False,
            env=environment,
        )
        assert_equal(0, stop_result.returncode, "Stop hook must exit cleanly.")
        assert_equal(
            {"continue": True},
            json.loads(stop_result.stdout),
            "Stop loop guard mismatch.",
        )


def run_hook_main(main, hook_input):
    previous_stdin = sys.stdin
    output = io.StringIO()
    try:
        sys.stdin = io.StringIO(json.dumps(hook_input))
        with redirect_stdout(output):
            exit_code = main()
    finally:
        sys.stdin = previous_stdin

    assert_equal(0, exit_code, "Hook main must exit cleanly.")
    return json.loads(output.getvalue()) if output.getvalue().strip() else None


def test_only_changed_classification_starts_continuation():
    wip_response = {
        "model": "jev-test",
        "answers": {
            "desired_label": {"choice": "wip", "confidence": 0.55},
        },
    }
    done_response = {
        "model": "jev-test",
        "answers": {
            "desired_label": {"choice": "done", "confidence": 0.55},
        },
    }
    previous_invoke = classify_title.invoke_jev_classification
    previous_plugin_data = os.environ.get("PLUGIN_DATA")
    previous_api_key = os.environ.get("TYPESAFE_API_KEY")

    with tempfile.TemporaryDirectory() as plugin_data:
        try:
            os.environ["PLUGIN_DATA"] = plugin_data
            os.environ["TYPESAFE_API_KEY"] = "test-key"
            requests = []
            responses = iter((wip_response, wip_response, done_response))

            def invoke(request, key):
                requests.append(request)
                return next(responses)

            classify_title.invoke_jev_classification = invoke

            first_prompt = {
                "session_id": "multi-turn-session",
                "prompt": "Investigate the first failure",
            }
            run_hook_main(capture_prompt.main, first_prompt)
            first_stop = run_hook_main(
                classify_title.main,
                {
                    "session_id": "multi-turn-session",
                    "stop_hook_active": False,
                    "last_assistant_message": "Investigation is in progress.",
                },
            )
            assert_equal("block", first_stop.get("decision"), "First turn must rename.")
            if "previous_label" in requests[0]["state"]:
                raise AssertionError("First turn must not send a previous label.")
            if "keep" in requests[0]["questions"]["desired_label"]["criteria"]:
                raise AssertionError("First turn must require an absolute label.")

            state_path = Path(plugin_data) / "sessions" / "multi-turn-session.json"
            first_state = json.loads(state_path.read_text(encoding="utf-8"))
            assert_equal(
                "wip",
                first_state["last_observed_label"],
                "Observed label diagnostics mismatch.",
            )
            assert_equal(
                0.55,
                first_state["last_observed_confidence"],
                "Observed confidence diagnostics mismatch.",
            )

            second_prompt = {
                "session_id": "multi-turn-session",
                "prompt": "Continue investigating the second failure",
            }
            run_hook_main(capture_prompt.main, second_prompt)
            second_stop = run_hook_main(
                classify_title.main,
                {
                    "session_id": "multi-turn-session",
                    "stop_hook_active": False,
                    "last_assistant_message": "Investigation is still in progress.",
                },
            )
            assert_equal(
                {"continue": True},
                second_stop,
                "An unchanged label must not spend a Codex continuation.",
            )
            if "previous_label" in requests[1]["state"]:
                raise AssertionError("Later turns must not anchor Jev to an old label.")

            third_prompt = {
                "session_id": "multi-turn-session",
                "prompt": "Finish the implementation",
            }
            run_hook_main(capture_prompt.main, third_prompt)
            third_stop = run_hook_main(
                classify_title.main,
                {
                    "session_id": "multi-turn-session",
                    "stop_hook_active": False,
                    "last_assistant_message": "Implementation is complete.",
                },
            )
            assert_equal(
                "block",
                third_stop.get("decision"),
                "A changed label must request a rename.",
            )
            assert_equal(3, len(requests), "Jev must still run once per real turn.")
        finally:
            classify_title.invoke_jev_classification = previous_invoke
            if previous_plugin_data is None:
                os.environ.pop("PLUGIN_DATA", None)
            else:
                os.environ["PLUGIN_DATA"] = previous_plugin_data
            if previous_api_key is None:
                os.environ.pop("TYPESAFE_API_KEY", None)
            else:
                os.environ["TYPESAFE_API_KEY"] = previous_api_key


def main():
    test_decision_policy()
    test_request_and_continuation_contract()
    test_hook_subprocess_contract()
    test_only_changed_classification_starts_continuation()
    print("Contract tests passed.")


if __name__ == "__main__":
    main()
