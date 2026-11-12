"""Generate a PBKDF2 password hash for OPERATOR_PASSWORD_HASH.

Usage (never commit the output — put it in the host's environment variables):

    python -m scripts.make_password_hash
"""
import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.auth import hash_password  # noqa: E402


def main() -> None:
    password = getpass.getpass("New operator password: ")
    confirm = getpass.getpass("Confirm: ")
    if password != confirm:
        print("Passwords do not match.")
        raise SystemExit(1)
    if len(password) < 12:
        print("Use at least 12 characters.")
        raise SystemExit(1)
    print("\nOPERATOR_PASSWORD_HASH=" + hash_password(password))
    print("\nSet this in the backend environment, not in git.")


if __name__ == "__main__":
    main()
