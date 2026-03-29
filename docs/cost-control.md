# Cost Control For The Single-VM Deployment

This project uses a budget notification pattern instead of a strict spend cap.

- Google Cloud budgets are not real-time hard stops.
- Budget notifications can arrive hours after spend is incurred.
- This billing account uses `INR`, so the current setup uses a conservative approximation of your `5 USD` goal.
- budget at `450 INR`
- VM stop action at `360 INR`

## Current Target

- Project: `discovery-intelligence-prod`
- Billing account: `019618-BC2AA5-8F774D`
- VM: `discovery-prod`
- Zone: `us-central1-a`
- Budget amount: `450 INR`
- Auto-stop threshold: `360 INR`

## What Gets Created

The setup script creates or updates:

- a Pub/Sub topic for budget notifications
- a dedicated Cloud Function that listens to that topic
- a dedicated service account for the function
- a project-scoped Cloud Billing budget connected to the topic

The function stops only the single VM instance `discovery-prod`.

## How To Apply

From the repo root:

```bash
bash scripts/setup_cost_controls.sh
```

## Important Limitations

- Stopping the VM reduces spend significantly, but it does not reduce spend to zero.
- Persistent disk charges continue while the disk exists.
- Static IP pricing can still apply depending on attachment and usage state.
- Budget notifications are not immediate, so final spend can exceed the stop threshold.
