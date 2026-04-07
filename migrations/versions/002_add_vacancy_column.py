"""Add vacancy column to employer_leads

Revision ID: 002
Revises: 001
Create Date: 2024-04-07

Adds vacancy column to store job title from discovery.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("employer_leads", sa.Column("vacancy", sa.String(500)))


def downgrade() -> None:
    op.drop_column("employer_leads", "vacancy")
