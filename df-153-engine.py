
# K16: Concurrent-Spawn-Mutex (fcntl-based, Trinity-CONSERVATIVE 2026-05-17)
def k16_lock_or_exit(df_name: str):
    """Acquire exclusive lock or exit(3). Prevents concurrent DF runs."""
    import fcntl, os, sys
    lock_path = f"/tmp/df-trinity-{df_name}.lock"
    fd = os.open(lock_path, os.O_CREAT | os.O_WRONLY)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return fd
    except BlockingIOError:
        sys.exit(3)


# K13: External-Anchor-Mock-RFC3161 (Trinity-CONSERVATIVE 2026-05-17)
def k13_anchor(payload_hash: str) -> dict:
    """Mock RFC3161-style timestamp anchor."""
    from datetime import datetime, timezone
    return {
        "anchor_type": "rfc3161-mock",
        "iso_ts": datetime.now(timezone.utc).isoformat(),
        "payload_hash": payload_hash,
    }


# K12: HMAC-SHA256-Provenance (Trinity-CONSERVATIVE 2026-05-17)
def k12_provenance(payload: bytes, key: bytes = b"df-trinity-conservative-v1") -> dict:
    """Returns payload_hash + HMAC-SHA256 signature."""
    import hashlib, hmac
    return {
        "payload_hash": hashlib.sha256(payload).hexdigest(),
        "hmac_sha256": hmac.new(key, payload, hashlib.sha256).hexdigest(),
    }

"""DF-153 engine for PVG-Cross-Entity-Revenue tracking."""

import re
import os
import json
import sys
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from datetime import datetime, timezone


DF_DIR = Path(__file__).parent
LOCK_DIR = Path("/tmp/df-153.lock")
DF_ID = "153"
DECISION_KEYWORDS_REGEX = re.compile(
    r"\b(entscheid[a-z]*|empfehl(?:e|en|t|st)|sollt(?:e|en|est)|recommend[a-z]*|decid[a-z]*|advis[a-z]*|propos[a-z]*)\b",
    re.IGNORECASE,
)


@dataclass
class TrackerOutput:
    welle: str = "25"
    df: str = "DF-153"
    iso_timestamp: str = ""
    source: str = "mock"
    heylou_revenue_eur: float = 0
    ndots_revenue_eur: float = 0
    lexvance_revenue_eur: float = 0
    cross_entity_total_eur: float = 0
    growth_per_entity: dict = field(default_factory=dict)


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _file_stable(path, min_age_sec=300) -> bool:
    target = Path(path)
    if not target.exists():
        return False
    try:
        age = time.time() - target.stat().st_mtime
    except OSError:
        return False
    return age >= min_age_sec


def acquire_lock_with_identity() -> bool:
    stale_after_sec = 6 * 60 * 60
    now = time.time()

    try:
        LOCK_DIR.mkdir(mode=0o700)
    except FileExistsError:
        try:
            lock_age = now - LOCK_DIR.stat().st_mtime
        except OSError:
            return False

        if lock_age <= stale_after_sec:
            return False

        try:
            for child in LOCK_DIR.iterdir():
                if child.is_file() or child.is_symlink():
                    child.unlink()
                elif child.is_dir():
                    child.rmdir()
            LOCK_DIR.rmdir()
            LOCK_DIR.mkdir(mode=0o700)
        except OSError:
            return False
    except OSError:
        return False

    identity = {
        "df_id": DF_ID,
        "pid": os.getpid(),
        "created_at": iso_now(),
        "cwd": os.getcwd(),
    }

    try:
        (LOCK_DIR / "identity.json").write_text(
            json.dumps(identity, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        os.utime(LOCK_DIR, None)
    except OSError:
        release_lock()
        return False

    return True


def release_lock() -> None:
    try:
        for child in LOCK_DIR.iterdir():
            if child.is_file() or child.is_symlink():
                child.unlink()
            elif child.is_dir():
                child.rmdir()
        LOCK_DIR.rmdir()
    except FileNotFoundError:
        return
    except OSError:
        return


def k17_pre_action_verification(anchors) -> dict:
    missing_anchors = []
    env_tag = os.environ.get("DF_153_ENV_TAG", "local")

    for anchor in anchors or []:
        anchor_text = str(anchor).strip()
        if not anchor_text:
            continue

        env_value = os.environ.get(anchor_text)
        path_exists = Path(anchor_text).exists()
        if env_value is None and not path_exists:
            missing_anchors.append(anchor_text)

    return {
        "ok": len(missing_anchors) == 0,
        "missing_anchors": missing_anchors,
        "env_tag": env_tag,
    }


def _is_real_api_enabled() -> bool:
    value = os.environ.get("DF_153_REAL_API_ENABLED", "false").strip().lower()
    return value in {"1", "true", "yes", "y", "on"}


def scan_output_for_decision_keywords(text) -> list:
    if text is None:
        return []
    return sorted({match.group(0) for match in DECISION_KEYWORDS_REGEX.finditer(str(text))})


def assert_no_decision_keywords(output) -> None:
    if isinstance(output, str):
        text = output
    else:
        text = json.dumps(output, ensure_ascii=False, sort_keys=True)

    matches = scan_output_for_decision_keywords(text)
    if matches:
        raise ValueError("Q_0/K_0 keyword block triggered: " + ", ".join(matches))


def _env_float(name: str, default: float = 0) -> float:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _env_json_dict(name: str) -> dict:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def collect_tracker_output() -> TrackerOutput:
    source = "real" if _is_real_api_enabled() else "mock"

    heylou = _env_float("DF_153_HEYLOU_REVENUE_EUR")
    ndots = _env_float("DF_153_NDOTS_REVENUE_EUR")
    lexvance = _env_float("DF_153_LEXVANCE_REVENUE_EUR")
    total = heylou + ndots + lexvance

    growth = _env_json_dict("DF_153_GROWTH_PER_ENTITY")
    if not growth:
        growth = {
            "heylou": _env_float("DF_153_HEYLOU_GROWTH", 0),
            "9dots": _env_float("DF_153_NDOTS_GROWTH", 0),
            "lexvance": _env_float("DF_153_LEXVANCE_GROWTH", 0),
        }

    return TrackerOutput(
        iso_timestamp=iso_now(),
        source=source,
        heylou_revenue_eur=heylou,
        ndots_revenue_eur=ndots,
        lexvance_revenue_eur=lexvance,
        cross_entity_total_eur=total,
        growth_per_entity=growth,
    )


def _anchors_from_env() -> list:
    raw = os.environ.get("DF_153_K17_ANCHORS", "")
    return [item.strip() for item in raw.split(",") if item.strip()]


def main() -> int:
    if not acquire_lock_with_identity():
        return 3

    try:
        pav = k17_pre_action_verification(_anchors_from_env())
        if not pav.get("ok"):
            report = {
                "df_id": DF_ID,
                "iso_timestamp": iso_now(),
                "status": "blocked",
                "k17_pre_action_verification": pav,
            }
            assert_no_decision_keywords(report)
            reports_dir = DF_DIR / "reports"
            reports_dir.mkdir(parents=True, exist_ok=True)
            date_part = datetime.now(timezone.utc).date().isoformat()
            report_path = reports_dir / f"df-153-{date_part}.json"
            report_path.write_text(
                json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True),
                encoding="utf-8",
            )
            return 3

        tracker_output = collect_tracker_output()
        payload = asdict(tracker_output)
        payload["k17_pre_action_verification"] = pav

        assert_no_decision_keywords(payload)

        reports_dir = DF_DIR / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        date_part = datetime.now(timezone.utc).date().isoformat()
        report_path = reports_dir / f"df-153-{date_part}.json"
        report_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        return 0
    except Exception as exc:
        sys.stderr.write(str(exc) + "\n")
        return 3
    finally:
        release_lock()


if __name__ == "__main__":
    sys.exit(main())