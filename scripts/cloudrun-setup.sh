#!/usr/bin/env bash
# One-time Google Cloud setup for the Buswise Cloud Run deploy workflow.
# Usage: bash scripts/cloudrun-setup.sh YOUR_PROJECT_ID   (safe to re-run)
# Needs: gcloud installed and logged in (gcloud auth login), billing enabled on the project.
set -euo pipefail

PROJECT_ID=${1:?Usage: bash scripts/cloudrun-setup.sh YOUR_PROJECT_ID}
REGION=us-central1               # Cloud Run's free allowance applies in some US regions
REPO_SLUG=abuhasif/BusWise-AI-Chatbot

gcloud config set project "$PROJECT_ID"
PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')

gcloud services enable run.googleapis.com artifactregistry.googleapis.com iamcredentials.googleapis.com compute.googleapis.com

# Networking for internal-only API and web services: the gateway sends its traffic
# through the default VPC, and Private Google Access lets it reach *.run.app from there.
gcloud compute networks describe default >/dev/null 2>&1 || gcloud compute networks create default --subnet-mode=auto
gcloud compute networks subnets update default --region="$REGION" --enable-private-ip-google-access

gcloud artifacts repositories describe buswise --location="$REGION" >/dev/null 2>&1 \
  || gcloud artifacts repositories create buswise --repository-format=docker --location="$REGION"

# Keep only the 2 newest versions of each image so storage stays inside the free 0.5 GB.
POLICY=$(mktemp)
cat > "$POLICY" <<'JSON'
[
  {"name": "keep-latest-2", "action": {"type": "Keep"}, "mostRecentVersions": {"keepCount": 2}},
  {"name": "delete-older", "action": {"type": "Delete"}, "condition": {"tagState": "any"}}
]
JSON
gcloud artifacts repositories set-cleanup-policies buswise --location="$REGION" --policy="$POLICY"
rm -f "$POLICY"

SA="github-deployer@$PROJECT_ID.iam.gserviceaccount.com"
gcloud iam service-accounts describe "$SA" >/dev/null 2>&1 || gcloud iam service-accounts create github-deployer
# networkUser lets the deployer attach the gateway to the VPC.
for role in roles/run.admin roles/artifactregistry.writer roles/iam.serviceAccountUser roles/compute.networkUser; do
  gcloud projects add-iam-policy-binding "$PROJECT_ID" --member="serviceAccount:$SA" --role="$role" --condition=None >/dev/null
done

gcloud iam workload-identity-pools describe github --location=global >/dev/null 2>&1 \
  || gcloud iam workload-identity-pools create github --location=global
gcloud iam workload-identity-pools providers describe github --location=global --workload-identity-pool=github >/dev/null 2>&1 \
  || gcloud iam workload-identity-pools providers create-oidc github \
       --location=global --workload-identity-pool=github \
       --issuer-uri=https://token.actions.githubusercontent.com \
       --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository" \
       --attribute-condition="assertion.repository=='$REPO_SLUG'"
gcloud iam service-accounts add-iam-policy-binding "$SA" \
  --role=roles/iam.workloadIdentityUser \
  --member="principalSet://iam.googleapis.com/projects/$PROJECT_NUMBER/locations/global/workloadIdentityPools/github/attribute.repository/$REPO_SLUG" >/dev/null

cat <<EOF

Done. Add these in GitHub -> Settings -> Secrets and variables -> Actions:

  Variables tab:
    GCP_PROJECT_ID = $PROJECT_ID
    GCP_REGION     = $REGION

  Secrets tab:
    GCP_WORKLOAD_IDENTITY_PROVIDER = projects/$PROJECT_NUMBER/locations/global/workloadIdentityPools/github/providers/github
    GCP_SERVICE_ACCOUNT            = $SA
    BUSWISE_API_TOKEN              = (run: openssl rand -hex 32)
    ONEMAP_EMAIL                   = your OneMap email
    ONEMAP_PASSWORD                = your OneMap password
EOF
