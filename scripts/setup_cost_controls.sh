#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-discovery-intelligence-prod}"
BILLING_ACCOUNT_ID="${BILLING_ACCOUNT_ID:-019618-BC2AA5-8F774D}"
REGION="${REGION:-us-central1}"
ZONE="${ZONE:-us-central1-a}"
INSTANCE_NAME="${INSTANCE_NAME:-discovery-prod}"
FUNCTION_NAME="${FUNCTION_NAME:-discovery-budget-stop}"
FUNCTION_RUNTIME="${FUNCTION_RUNTIME:-python311}"
FUNCTION_SOURCE="${FUNCTION_SOURCE:-infra/gcp/budget_stop_function}"
TOPIC_NAME="${TOPIC_NAME:-discovery-budget-notifications}"
SERVICE_ACCOUNT_ID="${SERVICE_ACCOUNT_ID:-discovery-budget-stop}"
SERVICE_ACCOUNT_EMAIL="${SERVICE_ACCOUNT_EMAIL:-${SERVICE_ACCOUNT_ID}@${PROJECT_ID}.iam.gserviceaccount.com}"
BILLING_CURRENCY="${BILLING_CURRENCY:-INR}"
BUDGET_DISPLAY_NAME="${BUDGET_DISPLAY_NAME:-Discovery Intelligence 450 INR Guardrail}"
BUDGET_AMOUNT="${BUDGET_AMOUNT:-450INR}"
STOP_THRESHOLD_AMOUNT="${STOP_THRESHOLD_AMOUNT:-360}"

PROJECT_NUMBER="${PROJECT_NUMBER:-$(gcloud projects describe "${PROJECT_ID}" --format='value(projectNumber)')}"
GCF_SERVICE_AGENT="service-${PROJECT_NUMBER}@gcf-admin-robot.iam.gserviceaccount.com"
TOPIC_RESOURCE="projects/${PROJECT_ID}/topics/${TOPIC_NAME}"

if ! command -v gcloud >/dev/null 2>&1; then
  echo "gcloud is required." >&2
  exit 1
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FUNCTION_SOURCE_PATH="${ROOT_DIR}/${FUNCTION_SOURCE}"

if [ ! -d "${FUNCTION_SOURCE_PATH}" ]; then
  echo "Function source directory not found: ${FUNCTION_SOURCE_PATH}" >&2
  exit 1
fi

echo "Enabling required Google Cloud APIs..."
gcloud services enable \
  billingbudgets.googleapis.com \
  cloudbilling.googleapis.com \
  pubsub.googleapis.com \
  cloudfunctions.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  --project "${PROJECT_ID}" \
  --quiet

echo "Ensuring Pub/Sub topic exists..."
if ! gcloud pubsub topics describe "${TOPIC_NAME}" --project "${PROJECT_ID}" >/dev/null 2>&1; then
  gcloud pubsub topics create "${TOPIC_NAME}" --project "${PROJECT_ID}"
fi

echo "Ensuring runtime service account exists..."
if ! gcloud iam service-accounts describe "${SERVICE_ACCOUNT_EMAIL}" --project "${PROJECT_ID}" >/dev/null 2>&1; then
  gcloud iam service-accounts create "${SERVICE_ACCOUNT_ID}" \
    --project "${PROJECT_ID}" \
    --display-name "Discovery budget stop runtime"
fi

echo "Granting the function permission to stop the VM..."
gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member "serviceAccount:${SERVICE_ACCOUNT_EMAIL}" \
  --role "roles/compute.instanceAdmin.v1" \
  --quiet >/dev/null

echo "Granting the Cloud Functions service agent Artifact Registry read access..."
gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member "serviceAccount:${GCF_SERVICE_AGENT}" \
  --role "roles/artifactregistry.reader" \
  --quiet >/dev/null

echo "Deploying the budget-stop function..."
gcloud functions deploy "${FUNCTION_NAME}" \
  --project "${PROJECT_ID}" \
  --region "${REGION}" \
  --runtime "${FUNCTION_RUNTIME}" \
  --entry-point "limit_use" \
  --trigger-topic "${TOPIC_NAME}" \
  --source "${FUNCTION_SOURCE_PATH}" \
  --service-account "${SERVICE_ACCOUNT_EMAIL}" \
  --set-env-vars "TARGET_PROJECT_ID=${PROJECT_ID},TARGET_ZONE=${ZONE},TARGET_INSTANCE_NAME=${INSTANCE_NAME},STOP_THRESHOLD_AMOUNT=${STOP_THRESHOLD_AMOUNT},BILLING_CURRENCY=${BILLING_CURRENCY}" \
  --memory "256MB" \
  --timeout "60s" \
  --quiet

echo "Creating or updating the project-scoped 5 USD budget..."
EXISTING_BUDGET_NAME="$(
  gcloud beta billing budgets list \
    --billing-account "${BILLING_ACCOUNT_ID}" \
    --format=json \
    | BUDGET_DISPLAY_NAME="${BUDGET_DISPLAY_NAME}" python3 -c '
import json, os, sys
built_display_name = os.environ["BUDGET_DISPLAY_NAME"]
budgets = json.load(sys.stdin)
for budget in budgets:
    if budget.get("displayName") == built_display_name:
        print(budget["name"].split("/")[-1])
        break
'
)"

if [ -n "${EXISTING_BUDGET_NAME}" ]; then
  gcloud beta billing budgets delete "${EXISTING_BUDGET_NAME}" \
    --billing-account "${BILLING_ACCOUNT_ID}" \
    --quiet
fi

gcloud beta billing budgets create \
  --billing-account "${BILLING_ACCOUNT_ID}" \
  --display-name "${BUDGET_DISPLAY_NAME}" \
  --budget-amount "${BUDGET_AMOUNT}" \
  --calendar-period month \
  --filter-projects "projects/${PROJECT_ID}" \
  --all-updates-rule-pubsub-topic "${TOPIC_RESOURCE}" \
  --threshold-rule "percent=0.8" \
  --threshold-rule "percent=1.0" \
  --quiet

echo
echo "Cost control setup complete."
echo "Budget: ${BUDGET_DISPLAY_NAME} (${BUDGET_AMOUNT}, monthly)"
echo "Auto-stop threshold inside function: ${STOP_THRESHOLD_AMOUNT} ${BILLING_CURRENCY}"
echo "Pub/Sub topic: ${TOPIC_RESOURCE}"
echo "Function: ${FUNCTION_NAME} (${REGION})"
