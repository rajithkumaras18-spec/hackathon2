# TruthChain

**TruthChain** is a full-stack web application that creates a tamper-evident chain of custody for digital media (images and short videos) by hashing raw media bytes, executing forensic AI deepfake detection, signing ledger entries with Ed25519 asymmetric cryptography, and exposing verification and full-chain validation tools.

Built for journalists, investigators, forensic analysts, content moderators, and compliance officers who require an auditable, cryptographically verifiable record that a media file existed at a point in time and what an AI detector estimated about its authenticity.

---

## Key Features

1. **Tamper-Evident Hash-Linked Custody Ledger**
   - Sequential cryptographic linkage where each entry seals `detector_score`, `file_hash`, `model_version`, `prev_record_hash`, and `timestamp`.
   - Genesis record rooted at 64 zeros (`0000000000000000000000000000000000000000000000000000000000000000`).
   - Deterministic canonical JSON key ordering for byte-level consistency.
   - Ed25519 asymmetric signatures generated over `record_hash` using the server's private key.
   - Seeded on initial run with 3 sample custody records.

2. **Forensic AI Deepfake Detection & Video Frame Sampling**
   - **Images (.jpg, .jpeg, .png)**: Analyzed for synthetic artifacts, gradient variance, noise, and probabilistic deepfake likelihood (0.0% – 100.0%).
   - **Videos (.mp4, max length 60s)**: Validated server-side via OpenCV (rejects clips > 60s); samples 1 frame per second of duration, evaluates per-frame probabilities, and calculates arithmetic mean.
   - **Model Fallback**: Attempts Hugging Face deepfake classification models first; smoothly falls back to a deterministic labeled scorer (`placeholder-v1`).
   - Scores always labeled with `"Detector scores are estimates, not proof."` and `"Model version: <model_version>"`.

3. **Cryptographic Chain Validation**
   - Explicit one-click audit tool on the Ledger page.
   - Recomputes canonical JSON and SHA-256 for every record, verifies `prev_record_hash` links, and checks Ed25519 signatures against server public key.
   - Green banner: `"Chain intact"`.
   - Red banner when broken: `"Chain broken at record <short_record_hash>: <reason>."`

4. **Media Verification (In-App & QR Code)**
   - Re-upload any media file or query a SHA-256 hash.
   - Match: `"Exact match, file unchanged since registration."` with original score and report downloads.
   - Mismatch: `"No match: this file was never registered or has been altered."` with quick register CTA.
   - Supports direct URL lookup `/verify?file_hash=<file_hash>` encoded in report QR codes.

5. **Tamper Detection Demonstration Laboratory**
   - Select any seeded or registered record and intentionally tamper stored database fields (such as changing fake probability) while retaining original signatures.
   - Visualizes immediate transition to amber status, broken link in chain visualization, and detection by Validate Chain.
   - One-click `"Restore"` reverts to backup copy.

6. **Downloadable Verification Reports**
   - **PDF Report**: High-resolution one-page printable verification report containing media thumbnail, full SHA-256 hash, detector score (`"NN.N% — estimate"`), model version, timestamp, Ed25519 signature, chain status banner, and scan-ready verification QR code.
   - **JSON Report**: Exact stored custody record structure.

7. **User Lifecycle & Cryptographic Identity**
   - User signup (password >= 8 chars), login, and password reset experience.
   - Account page displays server's public Ed25519 key fingerprint (short hex) for public transparency.

---

## Project Structure

```
truthchain/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app initialization, routes, mounting
│   ├── config.py            # App settings and paths
│   ├── crypto.py            # Ed25519 key management, canonical JSON, SHA-256 hashing
│   ├── detector.py          # AI deepfake detector with HF attempt & placeholder-v1 fallback, OpenCV video sampling
│   ├── database.py          # SQLite schema, connection, migrations, seeding 3 sample records
│   ├── reports.py           # PDF (ReportLab) & JSON report generation, QR code generation
│   ├── routes/
│   │   ├── auth.py          # Signup, login, logout, account profile, server key fingerprint
│   │   ├── upload.py        # File upload, SHA-256, OpenCV video validation & sampling, AI detector
│   │   ├── ledger.py        # Add to ledger, list ledger, record details, validate chain, tamper demo, restore
│   │   ├── verify.py        # Verify file or hash lookup
│   │   └── reports.py       # Download JSON & PDF verification reports
│   └── static/              # Polished dark security/forensics SPA
│       ├── index.html       # Single-page interface with responsive layout & modals
│       ├── css/
│       │   └── style.css    # High-contrast charcoal styling, gauges, timeline, chain graph
│       └── js/
│           ├── api.js       # Client API abstraction
│           ├── app.js       # Core routing, state, notification toasts, help tooltips
│           ├── upload.js    # Drag-and-drop, video preview, gauge animation
│           ├── ledger.js    # Timeline & Table views, detail drawer, chain visualizer
│           ├── verify.js    # File verification & QR code hash handling
│           ├── tamper.js    # Tamper & restore demo modal & controls
│           └── account.js   # Account info, display name rotation, key fingerprint
├── storage/
│   ├── uploads/             # Persisted media uploads
│   ├── thumbs/              # Generated thumbnails
│   └── truthchain.db        # SQLite database
├── requirements.txt
├── run.py                   # Server launcher
├── test_truthchain.py       # Comprehensive 9-part test suite
└── README.md
```

---

## How to Run

### 1. Requirements
Ensure Python 3.10+ (tested on Python 3.14) is installed. Dependencies:
```bash
pip install -r requirements.txt
```

### 2. Launch the Application
Start the server using `run.py`:
```bash
python run.py
```
Or with Uvicorn:
```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open your browser to:
[http://127.0.0.1:8000](http://127.0.0.1:8000)

### 3. Run Automated Tests
Execute the comprehensive test suite verifying hashing, signatures, seeded records, OpenCV video sampling, tamper detection, and reports:
```bash
python test_truthchain.py
```
