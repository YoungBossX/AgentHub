from typing import Optional
from uuid import uuid4

from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field


class ContactCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", max_length=120)
    company: Optional[str] = Field(default=None, max_length=120)
    status: str = Field(default="lead", max_length=40)


class Contact(ContactCreate):
    model_config = ConfigDict(from_attributes=True)

    id: str


class HealthResponse(BaseModel):
    status: str
    service: str


app = FastAPI(title="AgentHub Demo API")

_contacts: list[Contact] = [
    Contact(
        id="demo-contact-1",
        name="Ada Lovelace",
        email="ada@example.com",
        company="Analytical Engines",
        status="active",
    ),
    Contact(
        id="demo-contact-2",
        name="Grace Hopper",
        email="grace@example.com",
        company="Compiler Labs",
        status="lead",
    ),
]


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", service="agenthub-demo-api")


@app.get("/contacts", response_model=list[Contact])
def list_contacts() -> list[Contact]:
    return list(_contacts)


@app.post("/contacts", response_model=Contact, status_code=status.HTTP_201_CREATED)
def create_contact(payload: ContactCreate) -> Contact:
    if any(contact.email == payload.email for contact in _contacts):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Contact email already exists.",
        )
    contact = Contact(id=f"contact-{uuid4()}", **payload.model_dump())
    _contacts.append(contact)
    return contact


def reset_contacts_for_tests() -> None:
    _contacts.clear()
    _contacts.extend(
        [
            Contact(
                id="demo-contact-1",
                name="Ada Lovelace",
                email="ada@example.com",
                company="Analytical Engines",
                status="active",
            ),
            Contact(
                id="demo-contact-2",
                name="Grace Hopper",
                email="grace@example.com",
                company="Compiler Labs",
                status="lead",
            ),
        ]
    )
