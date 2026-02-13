"""Tests for units API endpoints."""


class TestGetUnits:
    def test_get_units(self, client):
        """Should return unit conversion factors."""
        response = client.get("/api/v1/units")
        assert response.status_code == 200
        data = response.json()

        # Check structure
        assert "weight" in data
        assert "volume" in data
        assert "count" in data
        assert "base_units" in data

        # Verify base units
        assert "g" in data["base_units"]
        assert "ml" in data["base_units"]
        assert "each" in data["base_units"]

        # Check some weight conversions
        assert data["weight"]["g"] == 1.0
        assert data["weight"]["kg"] == 1000.0
        assert data["weight"]["lb"] == 453.592
        assert data["weight"]["oz"] == 28.3495

        # Check some volume conversions
        assert data["volume"]["ml"] == 1.0
        assert data["volume"]["L"] == 1000.0
        assert data["volume"]["gal"] == 3785.41

        # Check count conversions
        assert data["count"]["each"] == 1.0
        assert data["count"]["doz"] == 12.0


class TestParsePack:
    def test_parse_standard_slash_format(self, client):
        """Should parse standard pack format like 36/1LB."""
        payload = {"description": "BUTTER AA 36/1LB CS"}
        response = client.post("/api/v1/units/parse-pack", json=payload)
        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert data["pack_count"] == 36.0
        assert data["unit_size"] == 1.0
        assert data["unit"].upper() == "LB"
        assert data["base_unit"] == "g"
        assert data["total_base_units"] is not None
        assert "display" in data

    def test_parse_gallon_format(self, client):
        """Should parse gallon format like 4/1GAL."""
        payload = {"description": "MILK 4/1GAL"}
        response = client.post("/api/v1/units/parse-pack", json=payload)
        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert data["pack_count"] == 4.0
        assert data["unit_size"] == 1.0
        assert data["base_unit"] == "ml"
        assert data["total_base_units"] == 4.0 * 3785.41

    def test_parse_fraction_format(self, client):
        """Should parse fraction format like 9/1/2GAL."""
        payload = {"description": "JUICE 9/1/2GAL"}
        response = client.post("/api/v1/units/parse-pack", json=payload)
        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert data["pack_count"] == 9.0
        assert data["unit_size"] == 0.5
        assert data["base_unit"] == "ml"

    def test_parse_x_format(self, client):
        """Should parse X format like 4X5LB."""
        payload = {"description": "CHEESE 4X5LB"}
        response = client.post("/api/v1/units/parse-pack", json=payload)
        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert data["pack_count"] == 4.0
        assert data["unit_size"] == 5.0
        assert data["base_unit"] == "g"

    def test_parse_dozen_format(self, client):
        """Should parse dozen format like 15DZ."""
        payload = {"description": "EGGS 15DZ"}
        response = client.post("/api/v1/units/parse-pack", json=payload)
        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert data["pack_count"] == 15.0
        assert data["unit_size"] == 12.0
        assert data["base_unit"] == "each"
        assert data["total_base_units"] == 180.0

    def test_parse_weight_case_format(self, client):
        """Should parse weight + case format like 10LB CS."""
        payload = {"description": "FLOUR 10LB CS"}
        response = client.post("/api/v1/units/parse-pack", json=payload)
        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert data["pack_count"] == 1.0
        assert data["unit_size"] == 10.0
        assert data["base_unit"] == "g"

    def test_parse_count_format(self, client):
        """Should parse count format like 4CT."""
        payload = {"description": "NAPKINS 4CT"}
        response = client.post("/api/v1/units/parse-pack", json=payload)
        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert data["pack_count"] == 4.0
        assert data["base_unit"] == "each"

    def test_parse_no_match(self, client):
        """Should return error for unparseable description."""
        payload = {"description": "SOMETHING RANDOM"}
        response = client.post("/api/v1/units/parse-pack", json=payload)
        assert response.status_code == 200
        data = response.json()

        assert data["success"] is False
        assert "error" in data
        assert data["error"] is not None

    def test_parse_empty_description(self, client):
        """Should return error for empty description."""
        payload = {"description": ""}
        response = client.post("/api/v1/units/parse-pack", json=payload)
        assert response.status_code == 200
        data = response.json()

        assert data["success"] is False
        assert "error" in data

    def test_parse_case_insensitive(self, client):
        """Should handle case-insensitive parsing."""
        payload1 = {"description": "4/1GAL"}
        payload2 = {"description": "4/1gal"}

        response1 = client.post("/api/v1/units/parse-pack", json=payload1)
        response2 = client.post("/api/v1/units/parse-pack", json=payload2)

        assert response1.status_code == 200
        assert response2.status_code == 200

        data1 = response1.json()
        data2 = response2.json()

        assert data1["success"] is True
        assert data2["success"] is True
        assert data1["total_base_units"] == data2["total_base_units"]

    def test_parse_decimal_unit_quantity(self, client):
        """Should parse decimal unit quantities like 6/1.5LB."""
        payload = {"description": "BACON 6/1.5LB"}
        response = client.post("/api/v1/units/parse-pack", json=payload)
        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert data["pack_count"] == 6.0
        assert data["unit_size"] == 1.5
        assert data["base_unit"] == "g"
        # 6 * 1.5 lb = 9 lb = 9 * 453.592 g
        assert abs(data["total_base_units"] - (9.0 * 453.592)) < 0.01

    def test_display_format_single_unit(self, client):
        """Should format display string for single unit."""
        payload = {"description": "10LB"}
        response = client.post("/api/v1/units/parse-pack", json=payload)
        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert "display" in data
        # Single unit shouldn't have "× " in display
        assert "×" not in data["display"] or data["pack_count"] > 1

    def test_display_format_multiple_units(self, client):
        """Should format display string for multiple units."""
        payload = {"description": "36/1LB"}
        response = client.post("/api/v1/units/parse-pack", json=payload)
        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert "display" in data
        # Multiple units should show pack count
        assert "36" in data["display"]
