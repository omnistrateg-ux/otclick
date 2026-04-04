"""Repository module for database operations."""

from app.storage.repositories.company_repo import CompanyRepository
from app.storage.repositories.contact_repo import ContactRepository
from app.storage.repositories.email_repo import EmailRepository
from app.storage.repositories.event_repo import EventRepository
from app.storage.repositories.lead_repo import LeadRepository

__all__ = [
    "LeadRepository",
    "CompanyRepository",
    "ContactRepository",
    "EventRepository",
    "EmailRepository",
]
