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
pip install -r requirements.txt
```

Start the web app:

```bash
uvicorn app:app --reload
```

Open `http://127.0.0.1:8000`.

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

- CSV uploads are inspected first so users can map columns before analysis runs.
- CSV uploads must include a mapped `smiles` column.
- Label aliases such as `biodegradable`, `label`, `target`, and `class` are accepted.
- The upload flow supports input type, intent, scoring mode, and consent selection.
- Labeled uploads are copied into `data/user_feedback.csv` only if the user explicitly allows learning.
- Each web run is archived under `data/uploads/<timestamp>/`.
- Each session writes `upload_session_summary.json`, `analysis_report.json`, `decision_output.json`, and `review_queue.json`.
- Session-specific pages are available at `/discovery?session_id=<id>` and `/dashboard?session_id=<id>`.

## Deploy On Render

Use these Render settings:

- Build command: `pip install -r requirements.txt`
- Start command: `uvicorn app:app --host 0.0.0.0 --port 10000`

Render should expose the FastAPI service directly. The dashboard is now integrated into the same FastAPI app, so no second dashboard service is required.

## Connect A Custom Domain

For the FastAPI app, attach your root or app subdomain in Render and point DNS for `imagewiz.info` or a chosen subdomain to the Render service.

If you still want to keep the legacy Streamlit dashboard around for internal use, it can remain separate, but the website no longer depends on it.

## Notes

- `GET /` renders the homepage.
- `GET /upload` renders the upload UI.
- `POST /api/upload/inspect` inspects a CSV and returns inferred mapping plus validation summary.
- `POST /api/upload/validate` refreshes validation against the selected mapping.
- `POST /upload` runs analysis and returns JSON.
- `GET /discovery` renders the ranked candidates table and review workflow.
- `POST /api/reviews` stores review actions.
- `GET /dashboard` renders the integrated dashboard.
- `GET /healthz` provides a simple deployment health check.
