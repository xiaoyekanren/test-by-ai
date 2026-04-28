import sys
sys.path.insert(0, 'backend')


def _create_workflow(client, name="test-wf", priority="P1", test_type="功能"):
    return client.post("/api/workflows", json={
        "name": name, "nodes": [], "edges": [],
        "priority": priority, "test_type": test_type,
    })


def _create_suite(client, name="test-suite"):
    return client.post("/api/test-suites", json={"name": name})


# ── List / Create ────────────────────────────────────────────

def test_list_suites_empty(client):
    r = client.get("/api/test-suites")
    assert r.status_code == 200
    assert r.json() == []


def test_create_suite(client):
    r = _create_suite(client)
    assert r.status_code == 201
    data = r.json()
    assert data["name"] == "test-suite"
    assert data["suite_type"] == "feature"
    assert data["case_count"] == 0


def test_create_suite_duplicate_name(client):
    _create_suite(client, "dup")
    r = _create_suite(client, "dup")
    assert r.status_code == 400


def test_list_suites_filter_type(client):
    client.post("/api/test-suites", json={"name": "s1", "suite_type": "smoke"})
    client.post("/api/test-suites", json={"name": "s2", "suite_type": "feature"})
    r = client.get("/api/test-suites", params={"suite_type": "smoke"})
    assert r.status_code == 200
    assert len(r.json()) == 1
    assert r.json()[0]["suite_type"] == "smoke"


# ── Get / Update / Delete ────────────────────────────────────

def test_get_suite(client):
    _create_suite(client)
    r = client.get("/api/test-suites/1")
    assert r.status_code == 200
    assert r.json()["name"] == "test-suite"
    assert "cases" in r.json()


def test_get_suite_not_found(client):
    r = client.get("/api/test-suites/999")
    assert r.status_code == 404


def test_update_suite(client):
    _create_suite(client)
    r = client.put("/api/test-suites/1", json={"name": "renamed"})
    assert r.status_code == 200
    assert r.json()["name"] == "renamed"


def test_delete_suite(client):
    _create_suite(client)
    r = client.delete("/api/test-suites/1")
    assert r.status_code == 204
    assert client.get("/api/test-suites/1").status_code == 404


# ── Add / Remove Cases ───────────────────────────────────────

def test_add_case(client):
    _create_suite(client)
    _create_workflow(client)
    r = client.post("/api/test-suites/1/cases", json={"workflow_id": 1})
    assert r.status_code == 200
    assert len(r.json()["cases"]) == 1
    assert r.json()["cases"][0]["workflow_id"] == 1


def test_add_case_duplicate(client):
    _create_suite(client)
    _create_workflow(client)
    client.post("/api/test-suites/1/cases", json={"workflow_id": 1})
    r = client.post("/api/test-suites/1/cases", json={"workflow_id": 1})
    assert r.status_code == 400


def test_add_case_workflow_not_found(client):
    _create_suite(client)
    r = client.post("/api/test-suites/1/cases", json={"workflow_id": 999})
    assert r.status_code == 404


def test_remove_case(client):
    _create_suite(client)
    _create_workflow(client)
    client.post("/api/test-suites/1/cases", json={"workflow_id": 1})
    r = client.delete("/api/test-suites/1/cases/1")
    assert r.status_code == 200
    assert len(r.json()["cases"]) == 0


def test_remove_case_not_in_suite(client):
    _create_suite(client)
    r = client.delete("/api/test-suites/1/cases/999")
    assert r.status_code == 404


# ── Reorder ──────────────────────────────────────────────────

def test_reorder_cases(client):
    _create_suite(client)
    _create_workflow(client, "wf1")
    _create_workflow(client, "wf2")
    client.post("/api/test-suites/1/cases", json={"workflow_id": 1})
    client.post("/api/test-suites/1/cases", json={"workflow_id": 2})

    r = client.put("/api/test-suites/1/cases/reorder", json=[2, 1])
    assert r.status_code == 200
    cases = r.json()["cases"]
    assert cases[0]["workflow_id"] == 2
    assert cases[1]["workflow_id"] == 1


def test_reorder_cases_invalid_id(client):
    _create_suite(client)
    _create_workflow(client)
    client.post("/api/test-suites/1/cases", json={"workflow_id": 1})
    r = client.put("/api/test-suites/1/cases/reorder", json=[1, 999])
    assert r.status_code == 400


# ── Cascade: delete suite removes cases ──────────────────────

def test_delete_suite_cascades_cases(client):
    _create_suite(client)
    _create_workflow(client)
    client.post("/api/test-suites/1/cases", json={"workflow_id": 1})
    r = client.delete("/api/test-suites/1")
    assert r.status_code == 204


# ── Cascade: delete workflow removes suite_cases ─────────────

def test_delete_workflow_cascades_suite_cases(client):
    _create_suite(client)
    _create_workflow(client)
    client.post("/api/test-suites/1/cases", json={"workflow_id": 1})
    r = client.delete("/api/workflows/1")
    assert r.status_code == 204
    detail = client.get("/api/test-suites/1")
    assert detail.status_code == 200
    assert len(detail.json()["cases"]) == 0


# ── Workflow test-case filters ───────────────────────────────

def test_list_workflows_is_test_case_filter(client):
    _create_workflow(client, "tc1", priority="P0")
    client.post("/api/workflows", json={"name": "plain-wf", "nodes": [], "edges": []})

    r = client.get("/api/workflows", params={"is_test_case": True})
    assert r.status_code == 200
    assert len(r.json()) == 1
    assert r.json()[0]["name"] == "tc1"

    r = client.get("/api/workflows", params={"is_test_case": False})
    assert len(r.json()) == 1
    assert r.json()[0]["name"] == "plain-wf"
