"""Verification: contract check + test runner + four-state decision (architecture §6)."""
import json
import shlex
import sqlite3
import subprocess
import sys


def decide_state(confidence: str, contract: str, tests: str) -> str:
    if confidence == "inferred":
        return "unknown"
    if contract == "fail" or tests == "fail":
        return "fail"
    if tests == "pass":
        return "pass"
    if contract == "pass" and tests == "not_run":
        return "not_run"
    return "unknown"


def run_test_cmd(cmd: str, cwd: str, timeout: int) -> tuple[str, str]:
    parts = cmd.split()
    module = parts[2] if len(parts) > 2 and parts[:2] == ["python", "-m"] else None
    if cmd.startswith("python "):
        cmd = shlex.quote(sys.executable) + cmd[6:]
    try:
        result = subprocess.run(
            cmd, shell=True, cwd=cwd,
            capture_output=True, text=True, timeout=timeout,
        )
        output = "\n".join((result.stdout + result.stderr).splitlines()[-30:])
        if result.returncode in (126, 127):
            # the shell could not find or execute the command: no test ran
            last = output.splitlines()[-1] if output else ""
            return "unknown", f"failed to start (exit {result.returncode}): {last}"
        if module and result.returncode != 0 and f"No module named {module}" in output:
            # e.g. pytest isn't installed next to Atlas: the tests never ran
            return "unknown", f"failed to start: {module} is not installed for {sys.executable}"
        state = "pass" if result.returncode == 0 else "fail"
        return state, output
    except subprocess.TimeoutExpired:
        return "unknown", f"timed out after {timeout} s"
    except OSError as e:
        return "unknown", f"failed to start: {e}"


def verify(
    conn: sqlite3.Connection,
    symbol: str,
    renamed_to: str | None = None,
    run_tests: bool = False,
    timeout: int = 120,
):
    from atlas.models import VerifyRow

    # All repos that expose the symbol (or renamed_to) as a field — these are producers
    producer_repos: set[str] = set()
    for s in ([symbol] + ([renamed_to] if renamed_to else [])):
        rows = conn.execute(
            "SELECT DISTINCT r.name FROM nodes n JOIN repos r ON r.id = n.repo_id "
            "WHERE n.kind = 'field' AND n.name = ?", (s,)
        ).fetchall()
        for row in rows:
            producer_repos.add(row[0])

    # Consumer repos (§6): any field_ref named symbol, or -- for renamed_to -- a field_ref with an
    # exact CONSUMES edge. Producers are never their own consumers.
    consumer_repos: set[str] = set()
    rows = conn.execute(
        "SELECT DISTINCT r.name FROM nodes n JOIN repos r ON r.id = n.repo_id "
        "WHERE n.kind = 'field_ref' AND n.name = ?", (symbol,)
    ).fetchall()
    consumer_repos.update(row[0] for row in rows)
    if renamed_to:
        rows = conn.execute(
            "SELECT DISTINCT r.name FROM nodes n JOIN repos r ON r.id = n.repo_id "
            "JOIN edges e ON e.src_id = n.id "
            "WHERE n.kind = 'field_ref' AND n.name = ? AND e.kind = 'CONSUMES' AND e.confidence = 'exact'",
            (renamed_to,),
        ).fetchall()
        consumer_repos.update(row[0] for row in rows)
    consumer_repos -= producer_repos

    if not consumer_repos:
        return []

    results: list[VerifyRow] = []

    for repo_name in sorted(consumer_repos):
        repo_row = conn.execute(
            "SELECT * FROM repos WHERE name = ?", (repo_name,)
        ).fetchone()
        if repo_row is None:
            continue
        repo_path = repo_row["path"]
        test_cmd = repo_row["test_cmd"]

        # refs_old: field_refs named symbol in this repo
        refs_old = conn.execute(
            "SELECT n.id, n.file, n.line FROM nodes n JOIN repos r ON r.id = n.repo_id "
            "WHERE n.kind = 'field_ref' AND n.name = ? AND r.name = ?",
            (symbol, repo_name),
        ).fetchall()

        # refs_new: field_refs named renamed_to in this repo
        refs_new = []
        if renamed_to:
            refs_new = conn.execute(
                "SELECT n.id, n.file, n.line FROM nodes n JOIN repos r ON r.id = n.repo_id "
                "WHERE n.kind = 'field_ref' AND n.name = ? AND r.name = ?",
                (renamed_to, repo_name),
            ).fetchall()

        # producer_has_old / producer_has_new
        producer_has_old = bool(conn.execute(
            "SELECT 1 FROM nodes n JOIN repos r ON r.id = n.repo_id "
            "WHERE n.kind = 'field' AND n.name = ? AND r.name != ?",
            (symbol, repo_name),
        ).fetchone())
        producer_has_new = False
        if renamed_to:
            producer_has_new = bool(conn.execute(
                "SELECT 1 FROM nodes n JOIN repos r ON r.id = n.repo_id "
                "WHERE n.kind = 'field' AND n.name = ? AND r.name != ?",
                (renamed_to, repo_name),
            ).fetchone())

        # confidence: exact if any CONSUMES edge from refs_old ∪ refs_new is exact (§6.3).
        # Documented extension: after a rename the old field no longer exists, so the linker cannot
        # create a CONSUMES edge for it. If the ref's file calls an endpoint that exposes `symbol`
        # or `renamed_to`, the link is still proven (a call, not a name guess) -> exact.
        all_ref_ids = [r["id"] for r in refs_old] + [r["id"] for r in refs_new]
        all_refs = list(refs_old) + list(refs_new)
        confidence = "inferred"
        best_ref = None
        if all_ref_ids:
            placeholders = ",".join("?" * len(all_ref_ids))
            exact_edge = conn.execute(
                f"SELECT e.confidence, n.file, n.line FROM edges e "
                f"JOIN nodes n ON n.id = e.src_id "
                f"WHERE e.kind = 'CONSUMES' AND e.src_id IN ({placeholders}) AND e.confidence = 'exact'",
                all_ref_ids,
            ).fetchone()
            if exact_edge:
                confidence = "exact"
                best_ref = (exact_edge["file"], exact_edge["line"])
            else:
                names = [symbol] + ([renamed_to] if renamed_to else [])
                name_marks = ",".join("?" * len(names))
                for ref_file in sorted({r["file"] for r in all_refs}):
                    calls = conn.execute(
                        "SELECT 1 FROM edges c "
                        "JOIN nodes src ON src.id = c.src_id "
                        "JOIN repos sr ON sr.id = src.repo_id "
                        "JOIN edges x ON x.src_id = c.dst_id AND x.kind = 'EXPOSES' "
                        "JOIN nodes fld ON fld.id = x.dst_id "
                        "WHERE c.kind = 'CALLS' AND src.file = ? AND sr.name = ? "
                        f"AND fld.name IN ({name_marks})",
                        (ref_file, repo_name, *names),
                    ).fetchone()
                    if calls:
                        confidence = "exact"
                        break
                first_ref = refs_old[0] if refs_old else refs_new[0]
                best_ref = (first_ref["file"], first_ref["line"])
        else:
            if refs_old:
                best_ref = (refs_old[0]["file"], refs_old[0]["line"])
            elif refs_new:
                best_ref = (refs_new[0]["file"], refs_new[0]["line"])

        evidence = f"{best_ref[0]}:{best_ref[1]}" if best_ref else "?"

        # contract (§6.4)
        if refs_old and not producer_has_old:
            contract = "fail"
            contract_reason = f"still references {symbol}, which no producer exposes"
        elif refs_old and producer_has_old:
            contract = "pass"
            contract_reason = f"{symbol} still exposed"
        elif not refs_old and refs_new and producer_has_new:
            contract = "pass"
            contract_reason = f"updated to {renamed_to}"
        else:
            contract = "n/a"
            contract_reason = "no contract to check"

        # tests (§6.5)
        test_output = ""
        if not run_tests:
            tests = "not_run"
            tests_detail = "tests not run"
        elif test_cmd is None:
            tests = "not_run"
            tests_detail = "no test command detected"
        else:
            tests, test_output = run_test_cmd(test_cmd, repo_path, timeout)
            # use the actual message from run_test_cmd (covers both timeout and OSError)
            tests_detail = test_output if tests == "unknown" else ""

        state = decide_state(confidence, contract, tests)

        # reason (§6.8)
        prefix = "name match only; " if confidence == "inferred" else ""
        suffix = ""
        if tests == "unknown" and tests_detail:
            suffix = f"; tests: {tests_detail}"
        reason = prefix + contract_reason + suffix

        results.append(VerifyRow(
            repo=repo_name,
            evidence=evidence,
            confidence=confidence,
            contract=contract,
            tests=tests,
            state=state,
            reason=reason,
            test_output=test_output,
        ))

    return results
