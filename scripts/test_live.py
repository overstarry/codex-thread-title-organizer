import json
import os

from common import invoke_jev_classification, new_jev_request, resolve_title_decision


def main():
    api_key = os.environ.get("TYPESAFE_API_KEY", "")
    if not api_key.strip():
        raise RuntimeError("TYPESAFE_API_KEY is not set.")

    request_body = new_jev_request(
        "Implement the agreed Codex thread title plugin using Jev.",
        "The implementation is complete and the contract tests passed.",
        os.environ.get("TYPESAFE_MODEL", "").strip() or "jev-latest",
    )
    response = invoke_jev_classification(request_body, api_key)
    decision = resolve_title_decision(response)
    if decision is None:
        raise RuntimeError("Jev returned no actionable title decision for the live fixture.")

    result = {
        "model": response.get("model"),
        "desired_label": response["answers"]["desired_label"]["choice"],
        "desired_label_confidence": response["answers"]["desired_label"]["confidence"],
        "selected_label": decision["label"],
        "selected_prefix": decision["prefix"],
    }
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))


if __name__ == "__main__":
    main()
