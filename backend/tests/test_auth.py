"""Authentication and organization foundation tests."""

import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app


@pytest.fixture(autouse=True)
def local_auth_mode():
    os.environ["AGENTSHIELD_AUTH_MODE"] = "local"
    get_settings.cache_clear()
    yield
    os.environ["AGENTSHIELD_AUTH_MODE"] = "disabled"
    get_settings.cache_clear()


client = TestClient(app)


def test_register_and_login():
    email = f"neworg-{uuid4().hex[:8]}@example.com"
    reg = client.post(
        "/api/v1/auth/register",
        json={
            "organization_name": "Acme Corp",
            "email": email,
            "password": "securepass123",
            "display_name": "Om Test",
        },
    )
    assert reg.status_code == 200, reg.text
    token = reg.json()["access_token"]
    assert reg.json()["user"]["role"] == "ORG_OWNER"
    assert reg.json()["user"]["organization_name"] == "Acme Corp"

    login = client.post("/api/v1/auth/login", json={"email": email, "password": "securepass123"})
    assert login.status_code == 200
    assert login.json()["access_token"]

    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == email


def test_duplicate_registration_rejected():
    email = f"dup-{uuid4().hex[:8]}@example.com"
    payload = {
        "organization_name": "Dup Org",
        "email": email,
        "password": "securepass123",
        "display_name": "Dup User",
    }
    assert client.post("/api/v1/auth/register", json=payload).status_code == 200
    dup = client.post("/api/v1/auth/register", json=payload)
    assert dup.status_code == 409


def test_organization_current():
    email = f"tenant-{uuid4().hex[:8]}@example.com"
    reg = client.post(
        "/api/v1/auth/register",
        json={
            "organization_name": "Tenant Test",
            "email": email,
            "password": "securepass123",
            "display_name": "Tenant User",
        },
    )
    token = reg.json()["access_token"]
    org = client.get("/api/v1/organizations/current", headers={"Authorization": f"Bearer {token}"})
    assert org.status_code == 200
    assert org.json()["name"] == "Tenant Test"
