"""Tests for distributor API endpoints."""
import uuid


class TestListDistributors:
    def test_list_empty(self, client, db):
        """Should return empty list when no distributors exist."""
        response = client.get("/api/v1/distributors")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 0
        assert data["distributors"] == []

    def test_list_with_distributors(self, client, distributor_factory):
        """Should return all active distributors."""
        dist1 = distributor_factory(name="Distributor A")
        dist2 = distributor_factory(name="Distributor B")
        distributor_factory(name="Inactive", is_active=False)

        response = client.get("/api/v1/distributors")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 2
        assert len(data["distributors"]) == 2
        names = [d["name"] for d in data["distributors"]]
        assert "Distributor A" in names
        assert "Distributor B" in names
        assert "Inactive" not in names

    def test_list_include_inactive(self, client, distributor_factory):
        """Should include inactive distributors when flag is set."""
        distributor_factory(name="Active")
        distributor_factory(name="Inactive", is_active=False)

        response = client.get("/api/v1/distributors?include_inactive=true")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 2
        names = [d["name"] for d in data["distributors"]]
        assert "Active" in names
        assert "Inactive" in names


class TestGetDistributor:
    def test_get_existing(self, client, distributor_factory):
        """Should return distributor details."""
        dist = distributor_factory(name="Test Distributor")

        response = client.get(f"/api/v1/distributors/{dist.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(dist.id)
        assert data["name"] == "Test Distributor"
        assert data["is_active"] is True

    def test_get_not_found(self, client, db):
        """Should return 404 for non-existent distributor."""
        fake_id = str(uuid.uuid4())
        response = client.get(f"/api/v1/distributors/{fake_id}")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


class TestCreateDistributor:
    def test_create_success(self, client, db):
        """Should create a new distributor."""
        payload = {
            "name": "New Distributor",
            "invoice_email": "invoices@example.com",
            "is_active": True,
        }

        response = client.post("/api/v1/distributors", json=payload)
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "New Distributor"
        assert data["invoice_email"] == "invoices@example.com"
        assert data["is_active"] is True
        assert "id" in data

    def test_create_duplicate_name(self, client, distributor_factory):
        """Should reject duplicate distributor names."""
        distributor_factory(name="Existing Distributor")

        payload = {"name": "Existing Distributor"}
        response = client.post("/api/v1/distributors", json=payload)
        assert response.status_code == 400
        assert "already exists" in response.json()["detail"].lower()

    def test_create_minimal(self, client, db):
        """Should create distributor with only required fields."""
        payload = {"name": "Minimal Distributor"}

        response = client.post("/api/v1/distributors", json=payload)
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Minimal Distributor"


class TestUpdateDistributor:
    def test_update_name(self, client, distributor_factory):
        """Should update distributor name."""
        dist = distributor_factory(name="Old Name")

        payload = {"name": "New Name"}
        response = client.patch(f"/api/v1/distributors/{dist.id}", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "New Name"

    def test_update_partial(self, client, distributor_factory):
        """Should update only provided fields."""
        dist = distributor_factory(name="Test", invoice_email="old@example.com")

        payload = {"invoice_email": "new@example.com"}
        response = client.patch(f"/api/v1/distributors/{dist.id}", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Test"  # Unchanged
        assert data["invoice_email"] == "new@example.com"  # Updated

    def test_update_not_found(self, client, db):
        """Should return 404 for non-existent distributor."""
        fake_id = str(uuid.uuid4())
        payload = {"name": "New Name"}
        response = client.patch(f"/api/v1/distributors/{fake_id}", json=payload)
        assert response.status_code == 404


class TestDeleteDistributor:
    def test_soft_delete(self, client, distributor_factory):
        """Should soft delete distributor (set is_active=False)."""
        dist = distributor_factory(name="To Delete")

        response = client.delete(f"/api/v1/distributors/{dist.id}")
        assert response.status_code == 204

        # Verify it's marked inactive
        get_response = client.get(f"/api/v1/distributors/{dist.id}")
        assert get_response.status_code == 200
        assert get_response.json()["is_active"] is False

    def test_delete_not_found(self, client, db):
        """Should return 404 for non-existent distributor."""
        fake_id = str(uuid.uuid4())
        response = client.delete(f"/api/v1/distributors/{fake_id}")
        assert response.status_code == 404
