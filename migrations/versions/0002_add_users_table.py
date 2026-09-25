"""add users table and link contacts to users

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-25 12:00:00

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: Union[str, Sequence[str], None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("username", sa.String(length=50), nullable=False),
        sa.Column("email", sa.String(length=100), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("avatar", sa.String(length=255), nullable=True),
        sa.Column(
            "confirmed", sa.Boolean(), server_default=sa.false(), nullable=False
        ),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=True
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
        sa.UniqueConstraint("username"),
    )

    # Contacts created before authentication existed have no owner and would be
    # unreachable through the API, so they are removed.
    op.execute("DELETE FROM contacts")

    op.add_column("contacts", sa.Column("user_id", sa.Integer(), nullable=False))
    op.create_foreign_key(
        "fk_contacts_user_id_users",
        "contacts",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(op.f("ix_contacts_user_id"), "contacts", ["user_id"], unique=False)

    # Contact email is now unique per user, not globally
    op.drop_constraint("contacts_email_key", "contacts", type_="unique")
    op.create_unique_constraint(
        "uq_contacts_email_user", "contacts", ["email", "user_id"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_contacts_email_user", "contacts", type_="unique")
    op.execute("DELETE FROM contacts")
    op.create_unique_constraint("contacts_email_key", "contacts", ["email"])
    op.drop_index(op.f("ix_contacts_user_id"), table_name="contacts")
    op.drop_constraint("fk_contacts_user_id_users", "contacts", type_="foreignkey")
    op.drop_column("contacts", "user_id")
    op.drop_table("users")
