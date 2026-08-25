import hashlib
import json
import os
import re
import sys
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
            "AppleWebKit/537.36 Chrome/131 Safari/537.36"
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

    # Remove things that normally don't represent the event/name.
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    text = soup.get_text("\n", strip=True)

    lines = [
        re.sub(r"\s+", " ", line).strip()
        for line in text.splitlines()
    ]

    lines = [line for line in lines if line]

    # Find lines containing "prelude", case-insensitive.
    matches = [
        line
        for line in lines
        if KEYWORD.casefold() in line.casefold()
    ]

    # Remove duplicates while preserving order.
    matches = list(dict.fromkeys(matches))

    return matches


def load_state():
    if not STATE_FILE.exists():
        return None

    try:
        return json.loads(STATE_FILE.read_text())
    except Exception:
        return None


def save_state(matches):
    STATE_FILE.write_text(
        json.dumps(
            {
                "matches": matches,
                "hash": hashlib.sha256(
                    json.dumps(
                        matches,
                        sort_keys=True,
                    ).encode()
                ).hexdigest(),
            },
            indent=2,
        )
    )


def send_notification(matches):
    message = (
        "Prelude detected/changed on SJYS.\n\n"
        + "\n".join(f"• {match}" for match in matches)
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


def main():
    try:
        html = fetch_page()
        matches = extract_matches(html)

        print("Matches found:")
        for match in matches:
            print(f"  {match}")

        previous = load_state()

        current_hash = hashlib.sha256(
            json.dumps(
                matches,
                sort_keys=True,
            ).encode()
        ).hexdigest()

        previous_hash = previous.get("hash") if previous else None

        # First run:
        # Save the current state but DON'T alert.
        if previous is None:
            print("First run - saving initial state without alert.")
            save_state(matches)
            return

        # No matching Prelude content.
        if not matches:
            print("No Prelude match.")
            save_state(matches)
            return

        # Matching content changed.
        if current_hash != previous_hash:
            print("CHANGE DETECTED - sending notification!")
            send_notification(matches)
            save_state(matches)
            return

        print("No change.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
