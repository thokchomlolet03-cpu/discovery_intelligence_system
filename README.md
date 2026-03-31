# Discovery Intelligence System

Discovery Intelligence is a molecular discovery web application built around the existing Python discovery engine in this repository. It is positioned as a decision-support system for prioritizing which molecules are worth testing next.

It supports two practical workflows:

- Full discovery mode for labeled uploads containing `smiles` plus a usable `biodegradable`/`label` column with both classes present.
- Prediction mode for unlabeled uploads, using the existing trained bundle in `rf_model_v1.joblib` to score uploaded molecules directly.

The web layer now includes:

- a guided inspect → validate → analyze upload flow
- session-specific discovery results and dashboard pages
- explicit consent handling for whether uploads may improve the system
- a native dashboard page inside the same FastAPI app
- review actions and review queue artifacts for chemist-facing triage

## What The System Does

- Featurizes molecules with RDKit descriptors and fingerprints.
- Trains or reuses a calibrated model for biodegradability scoring.
- Generates or ranks candidate molecules.
- Produces confidence, uncertainty, novelty, and experiment value scores.
- Shows live discovery outputs and an integrated dashboard.
- Queues labeled user submissions into `data/user_feedback.csv` only when explicit consent is granted.
- Stores review actions and review queues in structured JSON/CSV artifacts.

## Project Structure

```text
.
├── app.py
├── system/
│   ├── dashboard_data.py
│   ├── explanation_engine.py
│   ├── provenance.py
│   ├── review_manager.py
│   ├── run_pipeline.py
│   ├── session_report.py
│   └── upload_parser.py
├── templates/
│   ├── base.html
│   ├── about.html
│   ├── index.html
│   ├── upload.html
│   ├── discovery.html
│   └── dashboard.html
├── static/
│   └── styles.css
├── data/
│   ├── decision_output.json
│   └── uploads/
└── requirements.txt
```

## Run Locally

Install dependencies:

```bash
python -m pip install -r requirements.txt
```

Start the web app:

```bash
python -m uvicorn app:app --reload
```

If you are using the checked-in virtual environment:

```bash
venv/bin/python -m uvicorn app:app --reload
```

Open `http://127.0.0.1:8000`.

## Production Deployment

The repository now includes a single-VM Docker/GHCR deployment foundation for:

- FastAPI app container
- PostgreSQL container on the same VM
- bind-mounted persistent artifact storage
- GitHub Actions CI/build/deploy from GitHub to the VM

Operator-facing deployment instructions are in [docs/deployment.md](docs/deployment.md).
For the exact first-time Google Cloud VM setup steps, use [docs/google-cloud-vm-checklist.md](docs/google-cloud-vm-checklist.md).
For the current budget-based VM auto-stop setup, use [docs/cost-control.md](docs/cost-control.md).

## Run Tests

The repository uses Python's built-in `unittest` test discovery.

```bash
python -m unittest discover -s tests -v
```

If you are using the checked-in virtual environment:

```bash
venv/bin/python -m unittest discover -s tests -v
```

## Upload Behavior

- Supported upload formats are `CSV`, `TSV`, `TXT` SMILES lists, and `SDF`.
- Every upload is parsed into a canonical ingestion shape before analysis runs.
- The upload flow supports three semantic modes: structure-only screening, measurement datasets, and labeled tabular datasets.
- Users can map semantic roles such as `smiles`, `value`, `label`, `entity_id`, `target`, and `assay`.
- Measurement uploads can derive labels with a threshold rule before the job starts.
- Labeled uploads are copied into `data/user_feedback.csv` only if the user explicitly allows learning.
- Each web run is archived under `data/uploads/<timestamp>/`.
- Each session writes `upload_session_summary.json`, `analysis_report.json`, `decision_output.json`, and `review_queue.json`.
- Discovery and Dashboard keep the active session in navigation and fall back to the latest completed workspace session when no `session_id` is selected.
- Saved sessions can reopen from dedicated artifacts or from nested payloads inside `result.json`, which makes older runs more durable across page reloads.
- Session-specific pages are available at `/discovery?session_id=<id>` and `/dashboard?session_id=<id>`.

## Notes

- `GET /` renders the homepage.
- `GET /upload` renders the upload UI.
- `POST /api/upload/inspect` inspects a supported file and returns inferred semantic mapping plus validation summary.
- `POST /api/upload/validate` refreshes validation against the selected mapping.
- `POST /upload` runs analysis and returns JSON.
- `GET /discovery` renders the ranked candidates table and review workflow.
- `POST /api/reviews` stores review actions.
- `GET /dashboard` renders the integrated dashboard.
- `GET /healthz` provides a simple deployment health check.
