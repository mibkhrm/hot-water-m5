"""Check LUMS hostel hot water and push alerts to a phone via ntfy.

Alerts when a warden logs a new check, and when the hostel turns hot.
Env vars: NTFY_TOPIC (required to send), HOSTEL (default M5).
Flags: --test  send a test notification and exit
       --force ignore the 6 am - 11 pm time window
"""

import json
import os
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

HOSTEL = os.environ.get("HOSTEL", "M5")
API_URL = f"https://reslife.lums.edu.pk/api/hot-water?hostel={HOSTEL}"
PAGE_URL = "https://reslife.lums.edu.pk/hot-water"
NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "").strip()
STATE_FILE = Path(__file__).with_name("state.json")
PKT = timezone(timedelta(hours=5))  # Pakistan has no daylight saving
USER_AGENT = "hostel-hot-water-alert/1.0"


def parse_time(value):
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def in_window(now):
    # 06:00 to 23:15, leaving room for GitHub's late-starting runs
    minutes = now.hour * 60 + now.minute
    return 6 * 60 <= minutes <= 23 * 60 + 15


def notify(title, message, priority=3, tags=None):
    if not NTFY_TOPIC:
        print(f"[no NTFY_TOPIC set] would send: {title} | {message}")
        return
    body = json.dumps({
        "topic": NTFY_TOPIC,
        "title": title,
        "message": message,
        "priority": priority,
        "tags": tags or [],
        "click": PAGE_URL,
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://ntfy.sh/",
        data=body,
        headers={"Content-Type": "application/json", "User-Agent": USER_AGENT},
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        print(f"sent ({resp.status}): {title}")


def fetch_hostel():
    req = urllib.request.Request(API_URL, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = json.load(resp)
    for h in data.get("hostels", []):
        if h.get("hostel") == HOSTEL:
            return h
    raise ValueError(f"hostel {HOSTEL} not in response")


def load_state():
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def main():
    args = set(sys.argv[1:])

    if os.environ.get("GITHUB_ACTIONS") and not NTFY_TOPIC:
        sys.exit("NTFY_TOPIC secret is missing - add it in repo Settings > Secrets and variables > Actions")

    if "--test" in args:
        notify(f"{HOSTEL} hot water alerts", "Test notification - your phone is set up!", tags=["white_check_mark"])
        return

    now = datetime.now(PKT)
    if "--force" not in args and not in_window(now):
        print(f"outside 6 am - 11 pm PKT ({now:%H:%M}), skipping")
        return

    try:
        hostel = fetch_hostel()
    except Exception as e:  # network hiccup: log, don't alert
        print(f"could not fetch API: {e}")
        return

    status = hostel.get("status", "unknown")
    zones = hostel.get("zones", [])
    new_state = {
        "status": status,
        "zones": {z["zone"]: (z.get("last_check") or {}).get("checked_at") for z in zones},
    }
    print(f"{HOSTEL}: {status} - {hostel.get('summary')}")

    old_state = load_state()
    if old_state is None:
        print("first run, saving state without alerting")
        STATE_FILE.write_text(json.dumps(new_state, indent=2) + "\n", encoding="utf-8")
        return

    # Which wings got a newer check than last time?
    newly_checked = []
    for z in zones:
        new_t = parse_time((z.get("last_check") or {}).get("checked_at"))
        old_t = parse_time(old_state.get("zones", {}).get(z["zone"]))
        if new_t and (old_t is None or new_t > old_t):
            newly_checked.append((z, new_t))

    became_hot = status == "hot" and old_state.get("status") != "hot"

    wings = ", ".join(f"{z.get('label') or z['zone']}: {z.get('status')}" for z in zones)
    checked_line = ""
    if newly_checked:
        latest = max(t for _, t in newly_checked).astimezone(PKT)
        checked_line = f"Warden checked at {latest:%I:%M %p}. "

    if became_hot:
        notify(
            f"{HOSTEL} water is HOT",
            f"{checked_line}{hostel.get('summary')} ({wings})",
            priority=5,
            tags=["fire"],
        )
    elif newly_checked:
        notify(
            f"{HOSTEL} checked - {wings}",
            f"{checked_line}{hostel.get('summary')}",
            priority=3,
            tags=["droplet"],
        )
    else:
        print("no change")

    if new_state != old_state:
        STATE_FILE.write_text(json.dumps(new_state, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
