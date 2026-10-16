"""Create private local configuration without overwriting existing work."""

import secrets
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from briefing import sample_data

ROOT = Path(__file__).resolve().parent


def main():
    config = ROOT / ".env"
    if config.exists():
        print("Kept your existing .env.")
    else:
        token = secrets.token_urlsafe(32)
        config.write_text(
            f"ASSISTANT_TOKEN={token}\n"
            "ASSISTANT_TIMEZONE=America/New_York\n"
            "ASSISTANT_DATA_FILE=data.json\nUSE_AI=false\n"
            "OPENAI_API_KEY=\nOPENAI_MODEL=\n", encoding="utf-8")
        print("Created .env with a new private assistant token.")
    data_path = ROOT / "data.json"
    if data_path.exists():
        print("Kept your existing data.json.")
    else:
        sample = sample_data(datetime.now(timezone.utc), ZoneInfo("America/New_York"))
        data_path.write_text(sample.model_dump_json(indent=2), encoding="utf-8")
        print("Created fictional sample data for today in data.json.")
    print("Next: python -m uvicorn main:app --host 127.0.0.1 --port 8000")
    print("For the iPhone LAN test, follow iphone-shortcut.md.")


if __name__ == "__main__":
    main()
