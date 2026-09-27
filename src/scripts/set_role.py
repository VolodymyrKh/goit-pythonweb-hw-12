"""Command-line tool to change a user's role.

The API route for changing roles is available only to administrators, so the
first administrator has to be appointed from the command line::

    uv run python -m src.scripts.set_role <username> admin

or, when the application runs in Docker Compose::

    docker compose exec app uv run --no-sync python -m src.scripts.set_role <username> admin
"""

import argparse
import asyncio

from src.database.db import sessionmanager
from src.database.models import Role
from src.repository.users import UserRepository
from src.services.cache import invalidate_user


async def set_role(username: str, role: Role) -> bool:
    """Set the role of the user with the given username.

    Args:
        username: Username of the user to update.
        role: New role.

    Returns:
        ``True`` if the user was found and updated.
    """
    async with sessionmanager.session() as session:
        repository = UserRepository(session)
        user = await repository.get_user_by_username(username)
        if user is None:
            return False
        await repository.update_role(user.id, role)
    await invalidate_user(username)
    return True


def main(argv: list[str] | None = None) -> int:
    """Parse the command line and run :func:`set_role`.

    Returns:
        Process exit code: 0 on success, 1 if the user does not exist.
    """
    parser = argparse.ArgumentParser(description="Change a user's role")
    parser.add_argument("username")
    parser.add_argument("role", choices=[role.value for role in Role])
    args = parser.parse_args(argv)

    if asyncio.run(set_role(args.username, Role(args.role))):
        print(f"User '{args.username}' now has role '{args.role}'")
        return 0
    print(f"User '{args.username}' not found")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
