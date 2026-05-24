from fastapi.testclient import TestClient

from app.main import app, reset_contacts_for_tests


def client() -> TestClient:
    reset_contacts_for_tests()
    return TestClient(app)


def test_health_endpoint() -> None:
    response = client().get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "agenthub-demo-api",
    }


def test_list_contacts_returns_seed_contacts() -> None:
    response = client().get("/contacts")

    assert response.status_code == 200
    contacts = response.json()
    assert [contact["email"] for contact in contacts] == [
        "ada@example.com",
        "grace@example.com",
    ]


def test_contacts_allows_local_preview_cors() -> None:
    response = client().options(
        "/contacts",
        headers={
            "Origin": "http://127.0.0.1:62947",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:62947"


def test_create_contact_appends_contact() -> None:
    api = client()

    response = api.post(
        "/contacts",
        json={
            "name": "Katherine Johnson",
            "email": "katherine@example.com",
            "company": "Flight Dynamics",
            "status": "active",
        },
    )

    assert response.status_code == 201
    created = response.json()
    assert created["id"].startswith("contact-")
    assert created["name"] == "Katherine Johnson"
    assert created["email"] == "katherine@example.com"

    contacts = api.get("/contacts").json()
    assert [contact["email"] for contact in contacts] == [
        "ada@example.com",
        "grace@example.com",
        "katherine@example.com",
    ]


def test_create_contact_rejects_duplicate_email() -> None:
    response = client().post(
        "/contacts",
        json={
            "name": "Ada Clone",
            "email": "ada@example.com",
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Contact email already exists."
