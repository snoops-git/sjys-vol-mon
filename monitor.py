import hashlib
import json
import os
import re
from pathlib import Path

import requests
from bs4 import BeautifulSoup

URL = "https://sjys.ivolunteer.com/"
KEYWORD = "prelude"
STATE_FILE = Path("state.json")

NTFY_TOPIC = os.environ["NTFY_TOPIC"]
NTFY_URL = f"https://ntfy.sh/{NTFY_TOPIC}"


def fetch_page():
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 "
            "(KHTML, like Gecko) "
            "Chrome/131.0 Safari/537.36"
        )
    }

    response = requests.get(
        URL,
        headers=headers,
        timeout=30,
    )

    response.raise_for_status()
    return response.text


def extract_matches(html):
    soup = BeautifulSoup(html, "html.parser")

    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    text = soup.get_text("\n", strip=True)

    lines = []

    for line in text.splitlines():
        line = re.sub(r"\s+", " ", line).strip()

        if line:
            lines.append(line)

    matches = [
        line
        for line in lines
        if KEYWORD.casefold() in line.casefold()
    ]

    # Remove duplicates while preserving order.
    return list(dict.fromkeys(matches))


def load_state():
    if not STATE_FILE.exists():
        return None

    try:
        return json.loads(STATE_FILE.read_text())
    except Exception:
        return None


def calculate_hash(matches):
    data = json.dumps(
        matches,
        sort_keys=True,
    )

    return hashlib.sha256(
        data.encode("utf-8")
    ).hexdigest()


def save_state(matches):
    state = {
        "matches": matches,
        "hash": calculate_hash(matches),
    }

    STATE_FILE.write_text(
        json.dumps(
            state,
            indent=2,
        )
    )


def send_notification(matches):
    message = (
        "Prelude detected/changed on SJYS.\n\n"
        + "\n".join(
            f"• {match}"
            for match in matches
        )
        + f"\n\n{URL}"
    )

    headers = {
        "Title": "SJYS Prelude Alert",
        "Priority": "5",
        "Tags": "rotating_light",
        "Click": URL,
    }

    response = requests.post(
        NTFY_URL,
        data=message.encode("utf-8"),
        headers=headers,
        timeout=30,
    )

    response.raise_for_status()

    print("Notification sent successfully.")


def main():
    print("Checking SJYS...")
    print(f"Looking for: {KEYWORD}")

    html = fetch_page()

    matches = extract_matches(html)

    print(f"Found {len(matches)} matching line(s).")

    for match in matches:
        print(f"  {match}")

    previous = load_state()

    current_hash = calculate_hash(matches)

    # First run: establish baseline.
    if previous is None:
        print("First run.")
        print("Saving baseline without sending notification.")

        save_state(matches)
        return

    previous_hash = previous.get("hash")

    # Nothing containing Prelude is currently present.
    if not matches:
        print("No Prelude match.")

        save_state(matches)
        return

    # Prelude content has appeared or changed.
    if current_hash != previous_hash:
        print("CHANGE DETECTED!")

        send_notification(matches)

        save_state(matches)
        return

    print("No change detected.")


if __name__ == "__main__":
    main()
