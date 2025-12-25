#!/usr/bin/env python3
"""Setup validation script for Google Calendar to Discord sync."""

import sys
from pathlib import Path


def check_file_exists(filepath: Path, description: str) -> bool:
    """Check if a file exists and report status."""
    exists = filepath.exists()
    status = "✓" if exists else "✗"
    print(f"{status} {description}: {filepath}")
    return exists


def main() -> int:
    """Run setup checks."""
    print("Google Calendar to Discord - Setup Validation")
    print("=" * 50)
    print()

    project_root = Path(__file__).parent.parent
    all_checks_passed = True

    # Check critical configuration files
    print("Configuration Files:")
    if not check_file_exists(project_root / ".env", ".env configuration file"):
        print("  → Copy .env.example to .env and configure it")
        all_checks_passed = False

    if not check_file_exists(project_root / "credentials.json", "Google OAuth2 credentials"):
        print("  → Download credentials.json from Google Cloud Console")
        all_checks_passed = False

    print()

    # Check source files
    print("Source Files:")
    check_file_exists(project_root / "src/gcal_to_discord/__init__.py", "Package init")
    check_file_exists(project_root / "src/gcal_to_discord/config.py", "Config module")
    check_file_exists(
        project_root / "src/gcal_to_discord/google_calendar.py", "Google Calendar client"
    )
    check_file_exists(project_root / "src/gcal_to_discord/discord_client.py", "Discord client")
    check_file_exists(project_root / "src/gcal_to_discord/main.py", "Main entry point")

    print()

    # Check if .env has required variables (if it exists)
    env_file = project_root / ".env"
    if env_file.exists():
        print("Environment Variables Check:")
        required_vars = ["DISCORD_BOT_TOKEN", "DISCORD_CHANNEL_ID"]

        env_content = env_file.read_text()

        for var in required_vars:
            if f"{var}=" in env_content:
                value = [line for line in env_content.split("\n") if line.startswith(f"{var}=")]
                if value and "your_" not in value[0].lower() and "here" not in value[0].lower():
                    print(f"✓ {var} is configured")
                else:
                    print(f"✗ {var} needs to be set (currently using placeholder)")
                    all_checks_passed = False
            else:
                print(f"✗ {var} is missing from .env")
                all_checks_passed = False

        print()

    # Summary
    print("=" * 50)
    if all_checks_passed:
        print("✓ All critical checks passed!")
        print("\nYou're ready to run: uv run gcal-to-discord")
        return 0
    else:
        print("✗ Some checks failed. Please review the items above.")
        print("\nSetup instructions: See README.md")
        return 1


if __name__ == "__main__":
    sys.exit(main())
