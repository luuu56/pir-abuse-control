# scripts/run_day62_correctness.py
import sys
import time
import json
import requests
import concurrent.futures
import traceback
from pathlib import Path

root_path = Path(__file__).resolve().parent.parent
sys.path.append(str(root_path))

from services.client.main import acquire_ticket, create_bound_request

VERIFIER_URL = "http://127.0.0.1:8002/api/v1/verifier/execute"
METRICS_URL = "http://127.0.0.1:8002/api/v1/verifier/metrics"

C_CYAN = "\033[96m"
C_GREEN = "\033[92m"
C_RED = "\033[91m"
C_YELLOW = "\033[93m"
C_RESET = "\033[0m"

N_TESTS = 100
STORM_CONCURRENCY = 50
MAX_EXCEPTION_LOG = 5


results_json = {
    "metadata": {
        "test_iterations": N_TESTS,
        "storm_concurrency": STORM_CONCURRENCY,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "description": "Functional Correctness Assertions and PIR Isolation Evidence",
    },
    "test_cases": {},
}


def add_hist(hist, key):
    key = str(key) if key is not None else "none"
    hist[key] = hist.get(key, 0) + 1


def add_exception(exceptions):
    if len(exceptions) < MAX_EXCEPTION_LOG:
        exceptions.append(traceback.format_exc())


def get_pir_hits():
    try:
        r = requests.get(METRICS_URL, timeout=3)
        body = r.json()
        m = body.get("metrics", body)
        return int(m.get("pir_invoked_total") or m.get("pir_invoked") or 0)
    except Exception as e:
        print(f"{C_YELLOW}[WARN] Cannot read PIR metrics: {e}{C_RESET}")
        return 0


def safe_post_json(url, payload, timeout=8):
    """
    Return: (status_code, body_dict, raw_text)

    This avoids treating HTTP 4xx / non-json responses as script errors.
    """
    resp = requests.post(url, json=payload, timeout=timeout)
    text = resp.text
    try:
        body = resp.json()
    except Exception:
        body = {}
    return resp.status_code, body, text


def get_decision(body):
    raw = (
        body.get("decision")
        or body.get("status")
        or body.get("result")
        or body.get("state")
        or ""
    )
    return str(raw).upper()


def get_reason(status_code, body):
    reason = body.get("reason")
    if reason:
        return str(reason)
    if status_code >= 400:
        return f"HTTP {status_code}"
    return "none"


def is_success(status_code, body):
    decision = get_decision(body)
    reason = str(body.get("reason", "")).lower()

    return (
        status_code == 200
        and (
            decision in {"SUCCESS", "ACCEPT", "ACCEPTED", "CONSUMED"}
            or "pir execution completed" in reason
        )
    )


def is_rejected(status_code, body):
    decision = get_decision(body)
    reason = str(body.get("reason", "")).lower()

    if status_code in {400, 401, 403, 409, 422}:
        return True

    return (
        decision in {"REJECT", "REJECTED", "DROP", "DROPPED", "ERROR"}
        or "invalid" in reason
        or "missing" in reason
        or "binding" in reason
        or "consumed" in reason
        or "replay" in reason
        or "used" in reason
        or "epoch" in reason
        or "expired" in reason
        or "stale" in reason
        or "inactive" in reason
        or "sig" in reason
        or "signature" in reason
        or "verify" in reason
        or "verification" in reason
    )


def corrupt_base64_signature(sig: str) -> str:
    """
    Corrupt a Base64-encoded RSA signature while preserving length
    and Base64 alphabet.

    Current Ticket field is `sigma`, not `signature`.
    """
    if not sig or not isinstance(sig, str):
        return sig

    chars = list(sig)
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"

    for i, c in enumerate(chars):
        if c in alphabet:
            chars[i] = "A" if c != "A" else "B"
            return "".join(chars)

    # Fallback: keep length unchanged.
    chars[0] = "A" if chars[0] != "A" else "B"
    return "".join(chars)


def print_result_and_record(
    key,
    name,
    expected,
    actual,
    errors,
    pir_hits=0,
    is_attack=True,
    reason_hist=None,
    exception_log=None,
):
    is_pass = abs(actual - expected) < 1e-9 and errors == 0

    # For attack tests, backend PIR must not be invoked.
    if is_attack and pir_hits > 0:
        is_pass = False

    status = f"{C_GREEN}[PASS]{C_RESET}" if is_pass else f"{C_RED}[FAIL]{C_RESET}"
    pir_str = f" | PIR Hits: {pir_hits}" if is_attack else f" | PIR Hits: {pir_hits} (Legit)"
    print(f"{status} {name:<30}: {actual:>5.1f}% (Expected: {expected:>5.1f}%){pir_str}")

    results_json["test_cases"][key] = {
        "test_name": name,
        "expected_rate_pct": expected,
        "actual_rate_pct": actual,
        "errors": errors,
        "pir_hits_recorded": pir_hits,
        "passed": is_pass,
        "is_attack_scenario": is_attack,
        "reason_hist": reason_hist or {},
        "exception_log": exception_log or [],
    }


def run_honest():
    pir_start = get_pir_hits()
    succ_count, err_count = 0, 0
    reason_hist, exceptions = {}, []

    for i in range(N_TESTS):
        try:
            t = acquire_ticket()
            req = create_bound_request(t, f"honest_query_{i}").model_dump(mode="json")
            status, body, _ = safe_post_json(VERIFIER_URL, req)

            if is_success(status, body):
                succ_count += 1

            add_hist(reason_hist, get_reason(status, body))

        except Exception:
            err_count += 1
            add_exception(exceptions)

    pir_end = get_pir_hits()

    print_result_and_record(
        "honest",
        "Honest Request Accept",
        100.0,
        (succ_count / N_TESTS) * 100,
        err_count,
        pir_end - pir_start,
        False,
        reason_hist,
        exceptions,
    )


def run_missing_ticket():
    pir_start = get_pir_hits()
    rej_count, err_count = 0, 0
    reason_hist, exceptions = {}, []

    for i in range(N_TESTS):
        try:
            t = acquire_ticket()
            req_dict = create_bound_request(t, f"missing_ticket_{i}").model_dump(mode="json")

            # Remove the ticket entirely.
            req_dict.pop("ticket", None)

            status, body, _ = safe_post_json(VERIFIER_URL, req_dict)

            if is_rejected(status, body):
                rej_count += 1

            add_hist(reason_hist, get_reason(status, body))

        except Exception:
            err_count += 1
            add_exception(exceptions)

    pir_end = get_pir_hits()

    print_result_and_record(
        "missing_ticket",
        "Missing Ticket Reject",
        100.0,
        (rej_count / N_TESTS) * 100,
        err_count,
        pir_end - pir_start,
        True,
        reason_hist,
        exceptions,
    )


def run_invalid_signature():
    pir_start = get_pir_hits()
    rej_count, err_count = 0, 0
    reason_hist, exceptions = {}, []

    for i in range(N_TESTS):
        try:
            t = acquire_ticket()
            req_dict = create_bound_request(t, f"invalid_sig_{i}").model_dump(mode="json")

            # Current Ticket field is `sigma`, not `signature`.
            req_dict["ticket"]["sigma"] = corrupt_base64_signature(req_dict["ticket"]["sigma"])

            status, body, _ = safe_post_json(VERIFIER_URL, req_dict)

            if is_rejected(status, body):
                rej_count += 1

            add_hist(reason_hist, get_reason(status, body))

        except Exception:
            err_count += 1
            add_exception(exceptions)

    pir_end = get_pir_hits()

    print_result_and_record(
        "invalid_sig",
        "Invalid Signature Reject",
        100.0,
        (rej_count / N_TESTS) * 100,
        err_count,
        pir_end - pir_start,
        True,
        reason_hist,
        exceptions,
    )


def run_expired_ticket():
    """
    Expired-ticket test for the current verifier implementation.

    The verifier checks epoch validity before signature verification.
    Therefore, to test the expired-ticket rejection branch, we modify only
    the ticket epoch to an inactive old epoch. The expected behavior is:
    REJECTED before PIR invocation, with reason such as "Ticket expired."
    """
    pir_start = get_pir_hits()
    rej_count, err_count = 0, 0
    reason_hist, exceptions = {}, []

    for i in range(N_TESTS):
        try:
            t = acquire_ticket()
            req_dict = create_bound_request(t, f"expired_query_{i}").model_dump(mode="json")

            old_epoch = max(0, int(req_dict["ticket"]["epoch_id"]) - 10)
            req_dict["ticket"]["epoch_id"] = old_epoch

            status, body, _ = safe_post_json(VERIFIER_URL, req_dict)
            reason = get_reason(status, body)

            if is_rejected(status, body) and (
                "expired" in reason.lower()
                or "epoch" in reason.lower()
                or "stale" in reason.lower()
                or "inactive" in reason.lower()
            ):
                rej_count += 1

            add_hist(reason_hist, reason)

        except Exception:
            err_count += 1
            add_exception(exceptions)

    pir_end = get_pir_hits()

    print_result_and_record(
        "expired_ticket",
        "Expired Ticket Reject",
        100.0,
        (rej_count / N_TESTS) * 100,
        err_count,
        pir_end - pir_start,
        True,
        reason_hist,
        exceptions,
    )


def run_tampered_binding():
    pir_start = get_pir_hits()
    rej_count, err_count = 0, 0
    reason_hist, exceptions = {}, []

    for i in range(N_TESTS):
        try:
            t = acquire_ticket()
            req_dict = create_bound_request(t, f"original_query_{i}").model_dump(mode="json")

            # Change payload after binding was generated.
            req_dict["query_payload"] = f"hacked_query_{i}"

            status, body, _ = safe_post_json(VERIFIER_URL, req_dict)

            if is_rejected(status, body):
                rej_count += 1

            add_hist(reason_hist, get_reason(status, body))

        except Exception:
            err_count += 1
            add_exception(exceptions)

    pir_end = get_pir_hits()

    print_result_and_record(
        "tampered_binding",
        "Tampered Binding Reject",
        100.0,
        (rej_count / N_TESTS) * 100,
        err_count,
        pir_end - pir_start,
        True,
        reason_hist,
        exceptions,
    )


def run_sequential_replay():
    rej_count, err_count = 0, 0
    replay_pir_hits = 0
    reason_hist, exceptions = {}, []

    for i in range(N_TESTS):
        try:
            t = acquire_ticket()
            req = create_bound_request(t, f"replay_query_{i}").model_dump(mode="json")

            first_status, first_body, _ = safe_post_json(VERIFIER_URL, req, timeout=8)

            if not is_success(first_status, first_body):
                err_count += 1
                add_hist(reason_hist, f"first_request_failed:{get_reason(first_status, first_body)}")
                continue

            pir_before_replay = get_pir_hits()
            replay_status, replay_body, _ = safe_post_json(VERIFIER_URL, req, timeout=8)
            pir_after_replay = get_pir_hits()

            if is_rejected(replay_status, replay_body):
                rej_count += 1

            add_hist(reason_hist, get_reason(replay_status, replay_body))
            replay_pir_hits += max(0, pir_after_replay - pir_before_replay)

        except Exception:
            err_count += 1
            add_exception(exceptions)

    print_result_and_record(
        "sequential_replay",
        "Sequential Replay Reject",
        100.0,
        (rej_count / N_TESTS) * 100,
        err_count,
        replay_pir_hits,
        True,
        reason_hist,
        exceptions,
    )


def run_concurrent_storm():
    pir_start = get_pir_hits()
    storm_success, storm_reject, storm_error = 0, 0, 0
    reason_hist, exceptions = {}, []

    try:
        t_storm = acquire_ticket()
        req_storm = create_bound_request(
            t_storm,
            f"storm_query_{int(time.time() * 1000)}",
        ).model_dump(mode="json")

        def fire_storm(worker_id):
            try:
                status, body, text = safe_post_json(VERIFIER_URL, req_storm, timeout=12)

                if is_success(status, body):
                    return "SUCCESS", get_reason(status, body)

                if is_rejected(status, body):
                    return "REJECTED", get_reason(status, body)

                return "ERROR", f"unknown_response: status={status}, body={body}, text={text[:120]}"

            except Exception as e:
                return "ERROR", f"{type(e).__name__}: {e}"

        with concurrent.futures.ThreadPoolExecutor(max_workers=STORM_CONCURRENCY) as executor:
            futures = [executor.submit(fire_storm, i) for i in range(STORM_CONCURRENCY)]

            for fut in concurrent.futures.as_completed(futures):
                decision, reason = fut.result()
                add_hist(reason_hist, reason)

                if decision == "SUCCESS":
                    storm_success += 1
                elif decision == "REJECTED":
                    storm_reject += 1
                else:
                    storm_error += 1

    except Exception:
        storm_error += 1
        add_exception(exceptions)

    pir_end = get_pir_hits()
    pir_hits = pir_end - pir_start

    storm_pass = (
        storm_success == 1
        and storm_reject == STORM_CONCURRENCY - 1
        and storm_error == 0
        and pir_hits == 1
    )

    status_str = f"{C_GREEN}[PASS]{C_RESET}" if storm_pass else f"{C_RED}[FAIL]{C_RESET}"
    print(
        f"{status_str} Concurrent Storm (N={STORM_CONCURRENCY}) : "
        f"{storm_success} SUCCESS, {storm_reject} REJECTED, {storm_error} ERROR "
        f"| PIR Hits: {pir_hits} (Expected: 1)"
    )

    results_json["test_cases"]["concurrent_storm"] = {
        "test_name": "Concurrent Replay Storm",
        "expected_success_count": 1,
        "actual_success_count": storm_success,
        "expected_reject_count": STORM_CONCURRENCY - 1,
        "actual_reject_count": storm_reject,
        "actual_error_count": storm_error,
        "pir_hits_recorded": pir_hits,
        "passed": storm_pass,
        "is_attack_scenario": True,
        "reason_hist": reason_hist,
        "exception_log": exceptions,
    }


def print_summary():
    print("\n" + "=" * 90)
    print(f"{C_CYAN}📊 Final Functional Correctness Summary{C_RESET}")
    print(f"{'Test Case':<32} | {'Status':<10} | {'Backend PIR Invoked?':<22}")
    print("-" * 90)

    for key, item in results_json["test_cases"].items():
        passed = item.get("passed", False)
        status = f"{C_GREEN}PASS{C_RESET}" if passed else f"{C_RED}FAIL{C_RESET}"

        if key == "honest":
            pir_desc = f"Yes ({item.get('pir_hits_recorded', 0)})"
        elif key == "concurrent_storm":
            pir_desc = f"Only one ({item.get('pir_hits_recorded', 0)})"
        else:
            pir_desc = "No" if item.get("pir_hits_recorded", 0) == 0 else f"YES ({item.get('pir_hits_recorded')})"

        print(f"{item.get('test_name', key):<32} | {status:<10} | {pir_desc:<22}")

    print("=" * 90)


def save_results():
    # Main output path.
    out_dir = root_path / "results" / "correctness"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "day62_functional_correctness_final.json"

    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(results_json, f, indent=4)

    # Compatibility copy: if your previous pipeline expects this path.
    legacy_dir = root_path / "results" / "microbenchmarks"
    legacy_dir.mkdir(parents=True, exist_ok=True)
    legacy_file = legacy_dir / "day62_functional_correctness_final.json"

    with open(legacy_file, "w", encoding="utf-8") as f:
        json.dump(results_json, f, indent=4)

    print(f"📁 Final correctness evidence saved to: {out_file}")
    print(f"📁 Compatibility copy saved to: {legacy_file}")


def run_correctness_eval():
    print(f"\n{C_CYAN}🛡️ [Day 62-H] Functional Correctness and PIR Isolation Validation{C_RESET}")
    print("Target: verify pre-computation rejection, replay resistance, and exactly-once redemption.")
    print("-" * 90)

    run_honest()
    run_missing_ticket()
    run_invalid_signature()
    run_expired_ticket()
    run_tampered_binding()
    run_sequential_replay()
    run_concurrent_storm()

    print_summary()
    save_results()


if __name__ == "__main__":
    run_correctness_eval()