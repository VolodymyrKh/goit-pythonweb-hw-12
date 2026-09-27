"""add user roles and refresh tokens

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-27 12:00:00

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003"
down_revision: Union[str, Sequence[str], None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

user_role = sa.Enum("user", "admin", name="user_role")


def upgrade() -> None:
    user_role.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "users",
        sa.Column("role", user_role, server_default="user", nullable=False),
    )
    op.add_column(
        "users", sa.Column("refresh_token_hash", sa.String(length=64), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("users", "refresh_token_hash")
    op.drop_column("users", "role")
    user_role.drop(op.get_bind(), checkfirst=True)
