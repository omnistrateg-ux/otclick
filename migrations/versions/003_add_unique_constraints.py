"""Add unique constraints for deduplication

Revision ID: 003
Revises: 002
Create Date: 2024-04-20

Adds unique constraints to prevent duplicate leads and contacts.
Also adds partial unique index for INN when present.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Remove duplicates before adding constraint
    # Keep only the most recent lead for each (company_name, domain) pair
    op.execute("""
        DELETE FROM employer_leads a
        USING employer_leads b
        WHERE a.id < b.id
        AND a.company_name = b.company_name
        AND COALESCE(a.domain, '') = COALESCE(b.domain, '')
    """)

    # Add unique constraint on (company_name, domain)
    # Using COALESCE for domain to handle NULLs
    op.create_index(
        "ix_employer_leads_company_domain_unique",
        "employer_leads",
        [sa.text("company_name"), sa.text("COALESCE(domain, '')")],
        unique=True,
    )

    # Add partial unique index on INN (only when not null)
    op.create_index(
        "ix_company_profiles_inn_unique",
        "company_profiles",
        ["inn"],
        unique=True,
        postgresql_where=sa.text("inn IS NOT NULL"),
    )

    # Add unique constraint on email per lead (prevent duplicate contacts)
    op.execute("""
        DELETE FROM employer_contacts a
        USING employer_contacts b
        WHERE a.id < b.id
        AND a.lead_id = b.lead_id
        AND a.email = b.email
        AND a.email IS NOT NULL
    """)

    op.create_index(
        "ix_employer_contacts_lead_email_unique",
        "employer_contacts",
        ["lead_id", "email"],
        unique=True,
        postgresql_where=sa.text("email IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_employer_contacts_lead_email_unique", "employer_contacts")
    op.drop_index("ix_company_profiles_inn_unique", "company_profiles")
    op.drop_index("ix_employer_leads_company_domain_unique", "employer_leads")
