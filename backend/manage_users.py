"""Small user-management CLI for when you're locked out of the app itself
(e.g. you lost the password seed.py printed) or don't want to wipe the
database with `seed.py --reset`.

Usage:
    python manage_users.py list
    python manage_users.py set-password <email> <new_password>
    python manage_users.py promote <email>          # make an existing user admin
    python manage_users.py create-admin <name> <email> <password>
"""
import sys

from models import db
from utils.security import hash_password


def list_users():
    for u in db.users().find({}, {"email": 1, "role": 1, "active": 1}):
        print(f"{u['email']:35s} {u['role']:10s} active={u.get('active', True)}")


def set_password(email: str, new_pw: str):
    if len(new_pw) < 8:
        print("password must be at least 8 characters")
        sys.exit(1)
    res = db.users().update_one(
        {"email": email.lower()},
        {"$set": {"password_hash": hash_password(new_pw), "active": True}},
    )
    print("updated" if res.matched_count else "no such user")


def promote(email: str):
    res = db.users().update_one({"email": email.lower()}, {"$set": {"role": "admin"}})
    print("promoted to admin" if res.matched_count else "no such user")


def create_admin(name: str, email: str, password: str):
    if len(password) < 8:
        print("password must be at least 8 characters")
        sys.exit(1)
    email = email.lower()
    if db.users().find_one({"email": email}):
        print("a user with that email already exists - use set-password or promote instead")
        sys.exit(1)
    db.users().insert_one(
        {
            "name": name,
            "email": email,
            "password_hash": hash_password(password),
            "role": "admin",
            "active": True,
            "created_at": db.utcnow(),
        }
    )
    print(f"created admin {email}")


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(1)
    cmd, rest = args[0], args[1:]
    if cmd == "list":
        list_users()
    elif cmd == "set-password" and len(rest) == 2:
        set_password(*rest)
    elif cmd == "promote" and len(rest) == 1:
        promote(*rest)
    elif cmd == "create-admin" and len(rest) == 3:
        create_admin(*rest)
    else:
        print(__doc__)
        sys.exit(1)
