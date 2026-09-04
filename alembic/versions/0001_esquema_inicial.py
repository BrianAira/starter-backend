"""Esquema inicial del contrato v2.

Crea usuarios, salas, butacas, eventos y retenciones, con el índice único
parcial que garantiza RET-001.

Revision ID: 0001
Revises:
"""

from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
    )
    op.create_table(
        "rooms",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("rows", sa.Integer(), nullable=False),
        sa.Column("columns", sa.Integer(), nullable=False),
    )
    op.create_table(
        "events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("room_id", sa.Integer(), sa.ForeignKey("rooms.id"), nullable=False),
        sa.Column("starts_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "seats",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("room_id", sa.Integer(), sa.ForeignKey("rooms.id"), nullable=False),
        sa.Column("label", sa.String(), nullable=False),
        sa.Column("row", sa.String(), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("x", sa.Integer(), nullable=False),
        sa.Column("y", sa.Integer(), nullable=False),
        sa.Column("sector", sa.String(), nullable=False),
    )
    op.create_index(
        "uq_seats_room_xy", "seats", ["room_id", "x", "y"], unique=True
    )
    op.create_table(
        "holds",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("event_id", sa.Integer(), sa.ForeignKey("events.id"), nullable=False),
        sa.Column("seat_id", sa.Integer(), sa.ForeignKey("seats.id"), nullable=False),
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
    )

    # Garantía de RET-001. El predicado no puede mirar el reloj: por eso el
    # vencimiento se escribe (status pasa a 'expired') antes de insertar.
    op.create_index(
        "uq_holds_event_seat_active",
        "holds",
        ["event_id", "seat_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('active','confirmed')"),
        sqlite_where=sa.text("status IN ('active','confirmed')"),
    )


def downgrade() -> None:
    op.drop_index("uq_holds_event_seat_active", table_name="holds")
    op.drop_table("holds")
    op.drop_index("uq_seats_room_xy", table_name="seats")
    op.drop_table("seats")
    op.drop_table("events")
    op.drop_table("rooms")
    op.drop_table("users")
