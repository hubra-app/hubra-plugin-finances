"""finance_year_reports: the annual accounts of a closed year, frozen

Revision ID: 5a8e2c4f7b13
Revises: 3d7b1e9a5c42
Create Date: 2026-11-11 15:00:00

"""

from alembic import op
import sqlalchemy as sa

from hubra.core.plugins.ops import has_table


# revision identifiers, used by Alembic.
revision = "5a8e2c4f7b13"
down_revision = "3d7b1e9a5c42"
branch_labels = None
depends_on = None


def upgrade():
    if has_table("finance_year_reports"):
        return
    op.create_table(
        "finance_year_reports",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("start", sa.Date(), nullable=False),
        sa.Column("report", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("start", name="uq_finance_year_reports_start"),
    )


def downgrade():
    op.drop_table("finance_year_reports")
