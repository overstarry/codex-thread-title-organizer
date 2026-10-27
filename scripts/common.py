import json
import os
import re
import sys
import tempfile
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


for stream in (sys.stdin, sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8")


API_URL = "https://api.typesafe.ai/v1/systemone"
KNOWN_PREFIXES = ("⏸", "👀", "✅", "🚧", "💡", "🐛", "💬", "🎨", "✨", "🛠️")
PREFIX_BY_LABEL = {
    "blocked": "⏸",
    "validate": "👀",
    "done": "✅",
    "wip": "🚧",
    "plan": "💡",
    "bug": "🐛",
    "chat": "💬",
    "art": "🎨",
    "feature": "✨",
    "ops": "🛠️",
}
NON_RETRYABLE_STATUS_CODES = {400, 401, 403, 404, 422}


def write_hook_json(value):
    print(json.dumps(value, ensure_ascii=False, separators=(",", ":")), flush=True)


def write_hook_diagnostic(message):
    print(f"thread-title-organizer: {message}", file=sys.stderr, flush=True)


def safe_session_id(session_id):
    return re.sub(r"[^A-Za-z0-9._-]", "_", session_id)


def session_state_path(plugin_data, session_id):
    return Path(plugin_data) / "sessions" / f"{safe_session_id(session_id)}.json"


def read_session_state(path):
    path = Path(path)
    if not path.is_file():
        return {}

    content = path.read_text(encoding="utf-8")
    if not content.strip():
        return {}

    value = json.loads(content)
    if not isinstance(value, dict):
        raise ValueError("Session state must be a JSON object.")
    return value


def write_session_state(path, state):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=str(path.parent),
            prefix=f"{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
            json.dump(state, temporary_file, ensure_ascii=False, indent=2)
            temporary_file.write("\n")
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
        os.replace(str(temporary_path), str(path))
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()


def limit_text(value, maximum_length=8000):
    if value is None or len(value) <= maximum_length:
        return value
    return value[:maximum_length]


def new_jev_request(
    user_prompt,
    assistant_message,
    model="jev-latest",
):
    criteria = {
        "blocked": (
            "Progress cannot continue without user input, approval, credentials, "
            "or an external state change. Do not use for ordinary uncertainty."
        ),
        "validate": (
            "The work is implemented or analyzed, but the assistant explicitly says "
            "that user acceptance, testing, or another verification step still remains."
        ),
        "done": (
            "The assistant is giving the final answer, reports the requested conclusion, "
            "or says the requested work is complete, including bounded limitations."
        ),
        "wip": (
            "The assistant is actively implementing, investigating, or executing "
            "the requested work."
        ),
        "plan": (
            "The thread is primarily planning, designing, researching, or "
            "evaluating options before implementation."
        ),
        "bug": (
            "Diagnosing or fixing incorrect behavior, failures, regressions, "
            "crashes, or performance defects."
        ),
        "chat": (
            "General discussion, question answering, explanation, or advice "
            "without a more specific production task."
        ),
        "art": (
            "Creating or editing visual design, images, illustrations, branding, "
            "or other creative media."
        ),
        "feature": (
            "Building or extending product behavior, application code, "
            "integrations, or automation."
        ),
        "ops": (
            "Infrastructure, deployment, runtime operations, observability, "
            "configuration, or incident response."
        ),
    }
    return {
        "state": {
            "user_prompt": limit_text(user_prompt),
            "assistant_message": limit_text(assistant_message),
        },
        "model": model,
        "questions": {
            "desired_label": {
                "type": "choice",
                "instructions": (
                    "Which single label best describes the thread after the assistant "
                    "response? Classify the current absolute state independently of any "
                    "previous title. Prefer explicit evidence in assistant_message. When "
                    "several labels apply, use this precedence: blocked, done, validate, "
                    "wip, plan, then the durable task kind."
                ),
                "criteria": criteria,
            },
        },
    }


def invoke_jev_classification(request_body, api_key):
    body = json.dumps(request_body, ensure_ascii=False).encode("utf-8")
    request = Request(
        API_URL,
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    maximum_attempts = 2
    for attempt in range(1, maximum_attempts + 1):
        try:
            with urlopen(request, timeout=12) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            if error.code in NON_RETRYABLE_STATUS_CODES or attempt == maximum_attempts:
                raise
        except (URLError, TimeoutError, OSError, json.JSONDecodeError):
            if attempt == maximum_attempts:
                raise
        time.sleep(0.3)

    raise RuntimeError("Jev request failed without an exception.")


def _title_observation(answer, source):
    if not isinstance(answer, dict):
        return None

    choice = str(answer.get("choice", ""))
    try:
        confidence = float(answer.get("confidence", 0.0))
    except (TypeError, ValueError):
        return None

    if choice not in PREFIX_BY_LABEL:
        return None

    return {
        "label": choice,
        "prefix": PREFIX_BY_LABEL[choice],
        "confidence": confidence,
        "source": source,
    }


def read_title_observation(response):
    answers = response.get("answers", {}) if isinstance(response, dict) else {}
    return _title_observation(answers.get("desired_label"), "desired_label")


def resolve_title_decision(
    response,
    confidence_threshold=0.45,
):
    observation = read_title_observation(response)
    if observation is None or observation["confidence"] < confidence_threshold:
        return None
    return observation


def new_rename_continuation(session_id, prefix, label):
    known_prefixes = " ".join(KNOWN_PREFIXES)
    return (
        "[thread-title-organizer] Use the native Codex thread tools only. "
        f"For the current root thread with session id '{session_id}', read its current "
        f"title, remove all leading organizer prefixes from this set: {known_prefixes}, "
        f"then prepend exactly '{prefix} ' to the remaining title. Keep the remaining "
        "title text unchanged. If the title already has exactly that normalized prefix, "
        "do nothing. Do not modify any other thread. "
        f"This classification is '{label}'. After the tool call, finish without an "
        "explanatory message."
    )
