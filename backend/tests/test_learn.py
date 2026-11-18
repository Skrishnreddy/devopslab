MID = "k8s-01-architecture"


def test_tracks_and_kubernetes_has_20_modules(authed):
    tracks = authed.get("/api/v1/learn/tracks").json()
    assert tracks[0]["id"] == "kubernetes" and tracks[0]["status"] == "available"
    assert len(tracks[0]["modules"]) == 20
    assert {t["id"] for t in tracks} >= {"linux", "docker", "terraform", "aws", "azure", "gitops"}
    assert all(t["status"] == "planned" for t in tracks[1:])


def test_progress_round_trip_and_summary(authed):
    ids = [m["id"] for m in authed.get("/api/v1/learn/tracks/kubernetes").json()["modules"][:5]]
    for mid in ids:
        r = authed.put(f"/api/v1/learn/modules/{mid}/progress", json={"status": "completed"})
        assert r.status_code == 200 and r.json()["completed_at"]
    t = authed.get("/api/v1/learn/tracks/kubernetes").json()
    assert t["progress"] == {"completed": 5, "total": 20, "percent": 25}
    s = authed.get("/api/v1/progress/summary").json()
    assert s["modules_completed"] == 5 and s["modules_total"] == 20 and s["overall_percent"] == 25
    assert "Pods" in s["skills"]
    authed.put(f"/api/v1/learn/modules/{ids[4]}/progress", json={"status": "not_started"})
    assert authed.get("/api/v1/learn/tracks/kubernetes").json()["progress"]["completed"] == 4


def test_activity_is_recorded_and_deduplicated(authed):
    authed.put(f"/api/v1/learn/modules/{MID}/progress", json={"status": "started"})
    authed.put(f"/api/v1/learn/modules/{MID}/progress", json={"status": "completed"})
    authed.put("/api/v1/learn/modules/k8s-02-pods/progress", json={"status": "started"})
    recent = authed.get("/api/v1/activity/recent").json()
    assert [a["ref_id"] for a in recent] == ["k8s-02-pods", MID]
    assert recent[1]["title"] == "Kubernetes: Kubernetes Architecture"


def test_unknown_module_and_track(authed):
    assert authed.put("/api/v1/learn/modules/nope/progress", json={"status": "completed"}).status_code == 404
    assert authed.get("/api/v1/learn/tracks/nope").json()["error"]["code"] == "not_found"
    assert authed.put(f"/api/v1/learn/modules/{MID}/progress", json={"status": "bogus"}).status_code == 422


def test_engineer_reads_are_real_and_empty(authed):
    assert authed.get("/api/v1/labs").json() == []
    assert authed.get("/api/v1/challenges/attempts").json() == []
    projects = authed.get("/api/v1/projects").json()
    assert projects[0]["id"] == "cloudmart" and len(projects) == 5
    assert len(authed.get("/api/v1/challenges").json()) == 15


def test_features_and_settings(authed):
    f = {x["id"]: x for x in authed.get("/api/v1/features").json()}
    assert f["dashboard"]["status"] == "available" and f["terminal"]["status"] == "planned"
    s = authed.get("/api/v1/settings").json()
    assert s["environment"]["kube_context"] == "kind-cloudmart" and s["ai"]["enabled"] is False
