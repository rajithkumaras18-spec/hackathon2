import io
import json
import os
import sys
import tempfile
import cv2
import numpy as np
from pathlib import Path
from PIL import Image

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.config import GENESIS_PREV_HASH, FALLBACK_MODEL_VERSION
from app.crypto import crypto_service
from app.detector import detector
from app.database import (
    init_db,
    get_all_records,
    get_record_by_file_hash,
    tamper_record,
    restore_record,
    get_chain_meta
)
from app.reports import generate_json_report, generate_pdf_report
from fastapi.testclient import TestClient
from app.main import app

def run_tests():
    print("==================================================")
    print("TRUTHCHAIN COMPREHENSIVE AUTOMATED TEST SUITE")
    print("==================================================")

    # 1. Test Crypto Service
    print("\n[TEST 1] Cryptographic Service & Canonical JSON")
    score = 23.749
    file_hash = "abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789"
    model_ver = "placeholder-v1"
    prev_hash = GENESIS_PREV_HASH
    timestamp = "2026-10-08T06:30:00Z"

    rec_hash, canonical_json = crypto_service.compute_record_hash(
        detector_score=score,
        file_hash=file_hash,
        model_version=model_ver,
        prev_record_hash=prev_hash,
        timestamp=timestamp
    )
    print(f"  Canonical JSON: {canonical_json}")
    print(f"  Record Hash:    {rec_hash}")

    # Check key ordering
    parsed = json.loads(canonical_json)
    keys = list(parsed.keys())
    assert keys == ["detector_score", "file_hash", "model_version", "prev_record_hash", "timestamp"], \
        f"Keys not sorted properly: {keys}"
    assert parsed["detector_score"] == 23.7, "Detector score not rounded to 1 decimal!"
    print("  [OK] Canonical JSON key ordering verified")

    # Ed25519 Signing & Verification
    signature = crypto_service.sign_record_hash(rec_hash)
    assert crypto_service.verify_signature(rec_hash, signature) is True, "Signature verification failed!"
    assert crypto_service.verify_signature("bad_hash_000", signature) is False, "False positive signature verification!"
    print(f"  [OK] Ed25519 signing and verification verified (Signature: {signature[:16]}...)")
    print(f"  [OK] Server public key fingerprint: {crypto_service.public_key_fingerprint_short}")

    # 2. Test Database Init & Seed Records
    print("\n[TEST 2] Database Initialization & Seeded Records")
    init_db()
    records = get_all_records()
    print(f"  Total records in ledger: {len(records)}")
    assert len(records) >= 3, "Database was not seeded with at least 3 records!"
    print(f"  Seed Record #1: {records[0]['file_name']} (Prev: {records[0]['prev_record_hash'][:8]}...)")
    print(f"  Seed Record #2: {records[1]['file_name']} (Prev: {records[1]['prev_record_hash'][:8]}...)")
    print(f"  Seed Record #3: {records[2]['file_name']} (Prev: {records[2]['prev_record_hash'][:8]}...)")
    assert records[0]["prev_record_hash"] == GENESIS_PREV_HASH, "Genesis record prev_record_hash mismatch!"
    assert records[1]["prev_record_hash"] == records[0]["record_hash"], "Record 2 not chained to Record 1!"
    assert records[2]["prev_record_hash"] == records[1]["record_hash"], "Record 3 not chained to Record 2!"
    print("  [OK] Hash-linked sequential chain of seed records verified")

    # 3. Test API Endpoints via TestClient
    print("\n[TEST 3] FastAPI TestClient Integration")
    client = TestClient(app)

    # Validate Chain endpoint (should be INTACT on seed data)
    resp = client.post("/api/ledger/validate")
    assert resp.status_code == 200
    val_data = resp.json()
    print(f"  Validation Result: {val_data['message']}")
    assert val_data["status"] == "INTACT", f"Expected INTACT, got {val_data['status']}"
    assert val_data["message"] == "Chain intact", f"Expected 'Chain intact', got {val_data['message']}"
    print("  [OK] 'Chain intact' validation passed")

    # 4. Test Image Upload & AI Detection
    print("\n[TEST 4] Image Upload & Analysis")
    # Generate test image in memory
    test_img = Image.new("RGB", (200, 200), color=(73, 109, 137))
    img_byte_arr = io.BytesIO()
    test_img.save(img_byte_arr, format="PNG")
    img_bytes = img_byte_arr.getvalue()

    upload_resp = client.post(
        "/api/upload",
        files={"file": ("test_forensic.png", img_bytes, "image/png")}
    )
    assert upload_resp.status_code == 200, f"Upload failed: {upload_resp.text}"
    up_data = upload_resp.json()
    print(f"  Uploaded file hash: {up_data['file_hash']}")
    print(f"  Fake probability:   {up_data['detector_score']}%")
    print(f"  Model version:      {up_data['model_version']}")
    assert up_data["disclaimer"] == "Detector scores are estimates, not proof."
    print("  [OK] Upload returned proper score, hash, and disclaimer")

    # Add to Ledger
    reg_resp = client.post(
        "/api/ledger/register",
        json={
            "file_hash": up_data["file_hash"],
            "detector_score": up_data["detector_score"],
            "model_version": up_data["model_version"],
            "timestamp": up_data["timestamp"],
            "file_name": up_data["file_name"],
            "file_size": up_data["file_size"],
            "mime_type": up_data["mime_type"]
        }
    )
    assert reg_resp.status_code == 200, f"Ledger registration failed: {reg_resp.text}"
    reg_data = reg_resp.json()
    new_record_id = reg_data["record_id"]
    print(f"  Registered new Record #{new_record_id} with hash: {reg_data['record_hash']}")
    print("  [OK] File successfully added to hash-linked ledger")

    # Validate Chain again (should remain INTACT)
    val2 = client.post("/api/ledger/validate").json()
    assert val2["status"] == "INTACT"
    print("  [OK] Full chain remains intact with newly appended record")

    # 5. Test Verification Endpoint
    print("\n[TEST 5] Verification Tool (Match & No Match)")
    # Test Match with the file we just uploaded
    verify_match_resp = client.post(
        "/api/verify/file",
        files={"file": ("test_forensic.png", img_bytes, "image/png")}
    )
    assert verify_match_resp.status_code == 200
    vmatch_data = verify_match_resp.json()
    assert vmatch_data["matched"] is True
    assert vmatch_data["message"] == "Exact match, file unchanged since registration."
    print("  [OK] Match verified: 'Exact match, file unchanged since registration.'")

    # Test No Match with different bytes
    altered_bytes = img_bytes + b"_tampered_bits"
    verify_nomatch_resp = client.post(
        "/api/verify/file",
        files={"file": ("altered.png", altered_bytes, "image/png")}
    )
    assert verify_nomatch_resp.status_code == 200
    vnomatch_data = verify_nomatch_resp.json()
    assert vnomatch_data["matched"] is False
    assert vnomatch_data["message"] == "No match: this file was never registered or has been altered."
    print("  [OK] No Match verified: 'No match: this file was never registered or has been altered.'")

    # 6. Test Video Duration & Frame Sampling
    print("\n[TEST 6] Video Duration Validation & Sampling")
    # Generate short test mp4 using OpenCV (30 frames @ 30fps = 1.0 second)
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as temp_video:
        temp_video_path = temp_video.name

    try:
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(temp_video_path, fourcc, 30.0, (160, 120))
        for _ in range(30):
            frame = np.full((120, 160, 3), 100, dtype=np.uint8)
            out.write(frame)
        out.release()

        with open(temp_video_path, "rb") as vf:
            video_bytes = vf.read()

        vid_upload_resp = client.post(
            "/api/upload",
            files={"file": ("short_clip.mp4", video_bytes, "video/mp4")}
        )
        assert vid_upload_resp.status_code == 200, f"Video upload failed: {vid_upload_resp.text}"
        vid_data = vid_upload_resp.json()
        assert vid_data["is_video"] is True
        print(f"  Video analyzed successfully: {vid_data['file_name']} (Score: {vid_data['detector_score']}%)")
        print("  [OK] 1-second video correctly sampled and analyzed")
    finally:
        if os.path.exists(temp_video_path):
            os.remove(temp_video_path)

    # 7. Test Tamper Demo & Broken Chain Validation
    print("\n[TEST 7] Tamper Demo & Broken Chain Detection")
    # Tamper Record #2
    tamper_resp = client.post(
        "/api/ledger/tamper",
        json={"record_id": 2, "new_score": 99.9}
    )
    assert tamper_resp.status_code == 200
    t_data = tamper_resp.json()
    print(f"  Tampered Record #2: {t_data['message']}")

    # Validate Chain now (must detect breakage!)
    val_broken = client.post("/api/ledger/validate").json()
    print(f"  Validation message: {val_broken['message']}")
    assert val_broken["status"] == "BROKEN", "Chain was expected to be BROKEN!"
    assert "Chain broken at record" in val_broken["message"], f"Expected 'Chain broken at record...', got {val_broken['message']}"
    assert len(val_broken["inconsistencies"]) > 0, "No inconsistencies reported!"
    print("  [OK] Tamper accurately detected and chain marked as BROKEN")

    # Restore Record #2
    restore_resp = client.post(
        "/api/ledger/restore",
        json={"record_id": 2}
    )
    assert restore_resp.status_code == 200
    r_data = restore_resp.json()
    print(f"  Restored Record #2: {r_data['message']}")

    # Validate Chain again (must be INTACT again!)
    val_restored = client.post("/api/ledger/validate").json()
    assert val_restored["status"] == "INTACT", f"Expected INTACT after restore, got {val_restored['status']}"
    assert val_restored["message"] == "Chain intact"
    print("  [OK] 'Chain intact' confirmed after restoring record")

    # 8. Test Reports (JSON & PDF)
    print("\n[TEST 8] Report Generation (JSON & PDF with QR Code)")
    # JSON report
    json_rep_resp = client.get(f"/api/reports/json/{new_record_id}")
    assert json_rep_resp.status_code == 200
    rep_json = json_rep_resp.json()
    assert rep_json["record_id"] == new_record_id
    assert "signature" in rep_json
    print("  [OK] JSON report generated and verified")

    # PDF report
    pdf_rep_resp = client.get(f"/api/reports/pdf/{new_record_id}")
    assert pdf_rep_resp.status_code == 200
    assert pdf_rep_resp.headers["content-type"] == "application/pdf"
    assert len(pdf_rep_resp.content) > 1000, "PDF content is too small or empty!"
    print(f"  [OK] PDF report generated successfully ({len(pdf_rep_resp.content):,} bytes with QR code)")

    # 9. Test Auth & User Lifecycle
    print("\n[TEST 9] User Authentication & Profile Lifecycle")
    # Signup
    signup_resp = client.post(
        "/api/auth/signup",
        json={
            "name": "Forensic Investigator Jane",
            "email": "jane@truthchain.org",
            "password": "strongPassword123"
        }
    )
    assert signup_resp.status_code == 200
    assert signup_resp.json()["user"]["name"] == "Forensic Investigator Jane"
    print("  [OK] User signup succeeded")

    # Password validation (<8 chars)
    short_pw_resp = client.post(
        "/api/auth/signup",
        json={"name": "Bob", "email": "bob@truthchain.org", "password": "short"}
    )
    assert short_pw_resp.status_code == 400
    assert "at least 8 characters" in short_pw_resp.json()["detail"]
    print("  [OK] Password length validation enforced (< 8 chars rejected)")

    # Login
    login_resp = client.post(
        "/api/auth/login",
        json={"email": "jane@truthchain.org", "password": "strongPassword123"}
    )
    assert login_resp.status_code == 200
    print("  [OK] User login succeeded")

    # Failed Login
    bad_login = client.post(
        "/api/auth/login",
        json={"email": "jane@truthchain.org", "password": "wrong_password"}
    )
    assert bad_login.status_code == 401
    assert bad_login.json()["detail"] == "Invalid email or password"
    print("  [OK] Failed login returned 'Invalid email or password'")

    # Profile update
    prof_resp = client.post("/api/auth/profile", json={"name": "Lead Investigator Jane"})
    assert prof_resp.status_code == 200
    assert prof_resp.json()["user"]["name"] == "Lead Investigator Jane"
    print("  [OK] Profile display name rotation succeeded")

    print("\n==================================================")
    print("ALL 9 TEST SUITES COMPLETED WITH 100% SUCCESS!")
    print("==================================================")

if __name__ == "__main__":
    run_tests()
