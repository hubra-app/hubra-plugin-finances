"""budgets.owner_id: the member responsible for a budget

Revision ID: 3d7b1e9a5c42
Revises: 8c2cf6ad6e72
Create Date: 2026-11-05 00:30:00

"""

from alembic import op
import sqlalchemy as sa

from hubra.core.plugins.ops import columns


# revision identifiers, used by Alembic.
revision = "3d7b1e9a5c42"
down_revision = "8c2cf6ad6e72"
branch_labels = None
depends_on = None


def upgrade():
    if "owner_id" in columns("budgets"):
        return
    with op.batch_alter_table("budgets", schema=None) as batch_op:
        batch_op.add_column(sa.Column("owner_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_budgets_owner_id", "members", ["owner_id"], ["id"], ondelete="SET NULL"
        )


def downgrade():
    if "owner_id" not in columns("budgets"):
        return
    with op.batch_alter_table("budgets", schema=None) as batch_op:
        batch_op.drop_constraint("fk_budgets_owner_id", type_="foreignkey")
        batch_op.drop_column("owner_id")
