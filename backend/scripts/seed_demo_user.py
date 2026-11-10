"""Demo user database seed script.

DISABLED BY DEFAULT. Only executes when explicitly passed --confirm or
when ALLOW_DEMO_SEED=true is set in the environment.

DISCLAIMER:
Demo user credentials created here are purely for local application testing
and are completely separate from PayPal Sandbox buyer/seller credentials.
"""

import argparse
import asyncio
import os
import sys
from motor.motor_asyncio import AsyncIOMotorClient

# Ensure backend package is in python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.config import get_settings
from app.core.security import hash_password
from app.models.user import User

DEMO_EMAIL = "demo@payflowai.com"
DEMO_PASSWORD = "DemoPassword2026!"
DEMO_NAME = "Demo Operator"
DEMO_BUSINESS = "Acme Consulting Studio"


async def seed_demo_user(force: bool = False) -> None:
    settings = get_settings()

    allow_env = os.getenv("ALLOW_DEMO_SEED", "false").lower() == "true"
    if not (force or allow_env):
        print(
            "ERROR: Demo seeding is disabled by default to prevent accidental data modification.\n"
            "To run, supply the '--confirm' flag or set environment variable 'ALLOW_DEMO_SEED=true'.\n"
            "Example: python scripts/seed_demo_user.py --confirm"
        )
        sys.exit(1)

    print(f"Connecting to MongoDB at {settings.MONGODB_URI}...")
    client = AsyncIOMotorClient(settings.MONGODB_URI, serverSelectionTimeoutMS=4000)
    db = client[settings.MONGODB_DATABASE]

    try:
        # Check if already exists
        existing = await db.users.find_one({"email": DEMO_EMAIL})
        if existing:
            print(f"Notice: Demo user '{DEMO_EMAIL}' already exists in database '{settings.MONGODB_DATABASE}'.")
            return

        hashed = hash_password(DEMO_PASSWORD)
        demo_user = User(
            email=DEMO_EMAIL,
            hashed_password=hashed,
            name=DEMO_NAME,
            business_name=DEMO_BUSINESS,
        )

        await db.users.insert_one(demo_user.model_dump())
        print("=" * 70)
        print("DEMO USER SEEDED SUCCESSFULLY")
        print(f"  Email:        {DEMO_EMAIL}")
        print(f"  Password:     {DEMO_PASSWORD}")
        print(f"  User ID:      {demo_user.id}")
        print("=" * 70)
        print(
            "IMPORTANT NOTICE:\n"
            "These demo credentials provide access ONLY to the local PAYFLOW AI application.\n"
            "They are completely separate from your PayPal Sandbox account and PayPal Sandbox\n"
            "buyer accounts (which must be created in https://developer.paypal.com)."
        )
        print("=" * 70)
    finally:
        client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed demo user into MongoDB.")
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Explicitly confirm demo seed execution.",
    )
    args = parser.parse_args()
    asyncio.run(seed_demo_user(force=args.confirm))
