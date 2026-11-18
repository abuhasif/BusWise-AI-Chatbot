# Deploying Buswise

Buswise ships as three containers: `api` (Python), `web` (React/vinext) and `gateway` (Express). Only the gateway needs a public URL. The Qwen model is optional: without Ollama the API runs in **limited mode** (rule-based intent parsing plus the SQLite snapshot), which is what the hosted demo uses.

## Choosing a host

| Option | Cost for a low-traffic demo | Notes |
| --- | --- | --- |
| **Google Cloud Run** (recommended, workflow included) | Free within the monthly always-free allowance | Scales to zero, deploys plain Docker images, HTTPS by default. Needs a billing account, and the free allowance applies only in some US regions. The first request after idle has a cold start of a few seconds. |
| Render (free web service) | Free | Simplest setup, but free services sleep after 15 minutes idle (about 1 minute to wake), and free services cannot receive private-network traffic. Set `API_URL`/`WEB_URL` to the other services' public `onrender.com` URLs. |
| AWS ECS (Fargate) Express Mode | Paid (Fargate tasks plus a load balancer, roughly $20–40/month). New-account AWS credits can cover a short demo. | The AWS-native path. App Runner closed to new customers on 30 April 2026, and AWS recommends ECS Express Mode instead. |

Check each provider's current pricing page before relying on these figures.

## Google Cloud Run (free tier)

The [`Deploy to Google Cloud Run`](../.github/workflows/deploy-cloudrun.yml) workflow builds the three images, pushes them to Artifact Registry and deploys them. It authenticates through Workload Identity Federation, so no JSON key is stored in GitHub.

### One-time setup

```bash
PROJECT_ID=your-project-id
REGION=us-central1
REPO_SLUG=abuhasif/BusWise-AI-Chatbot
PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')

gcloud config set project "$PROJECT_ID"
gcloud services enable run.googleapis.com artifactregistry.googleapis.com iamcredentials.googleapis.com

gcloud artifacts repositories create buswise --repository-format=docker --location="$REGION"

# Service account that GitHub Actions will impersonate
gcloud iam service-accounts create github-deployer
SA="github-deployer@$PROJECT_ID.iam.gserviceaccount.com"
for role in roles/run.admin roles/artifactregistry.writer roles/iam.serviceAccountUser; do
  gcloud projects add-iam-policy-binding "$PROJECT_ID" --member="serviceAccount:$SA" --role="$role"
done

# Trust GitHub's OIDC tokens for this repository only
gcloud iam workload-identity-pools create github --location=global
gcloud iam workload-identity-pools providers create-oidc github \
  --location=global --workload-identity-pool=github \
  --issuer-uri=https://token.actions.githubusercontent.com \
  --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository" \
  --attribute-condition="assertion.repository=='$REPO_SLUG'"
gcloud iam service-accounts add-iam-policy-binding "$SA" \
  --role=roles/iam.workloadIdentityUser \
  --member="principalSet://iam.googleapis.com/projects/$PROJECT_NUMBER/locations/global/workloadIdentityPools/github/attribute.repository/$REPO_SLUG"

echo "GCP_WORKLOAD_IDENTITY_PROVIDER=projects/$PROJECT_NUMBER/locations/global/workloadIdentityPools/github/providers/github"
echo "GCP_SERVICE_ACCOUNT=$SA"
```

In GitHub, open **Settings → Secrets and variables → Actions** and add:

- Variables: `GCP_PROJECT_ID`, and optionally `GCP_REGION` (defaults to `us-central1`)
- Secrets: `GCP_WORKLOAD_IDENTITY_PROVIDER` and `GCP_SERVICE_ACCOUNT` (printed above), `BUSWISE_API_TOKEN` (any random string of 32+ characters, for example `openssl rand -hex 32`), and optionally `ONEMAP_EMAIL` and `ONEMAP_PASSWORD` (your OneMap account, for live routing)

Then run **Actions → Deploy to Google Cloud Run → Run workflow**. The job summary prints the public gateway URL.

To keep costs at zero, set a [budget alert](https://cloud.google.com/billing/docs/how-to/budgets) on the billing account. The workflow caps each service at two instances.

## AWS (ECS Express Mode)

1. Push the three images to Amazon ECR:

   ```bash
   AWS_REGION=ap-southeast-1
   ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
   REGISTRY=$ACCOUNT.dkr.ecr.$AWS_REGION.amazonaws.com
   aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $REGISTRY
   for image in api web gateway; do aws ecr create-repository --repository-name buswise-$image --region $AWS_REGION || true; done
   docker build -f backend/Dockerfile -t $REGISTRY/buswise-api:latest .
   docker build -f Dockerfile.web -t $REGISTRY/buswise-web:latest .
   docker build -t $REGISTRY/buswise-gateway:latest gateway
   for image in api web gateway; do docker push $REGISTRY/buswise-$image:latest; done
   ```

2. In the ECS console, create an Express Mode service for each image (ports 8765, 3000 and 8080) with the same environment variables as [`docker-compose.yml`](../docker-compose.yml). Point the gateway's `API_URL` and `WEB_URL` at the other two services' URLs, and keep `BUSWISE_API_TOKEN` in AWS Secrets Manager.
3. Delete the services when the demo is over. The load balancer is billed while it exists.

## Environment variables

| Service | Variable | Purpose |
| --- | --- | --- |
| api | `BUSWISE_API_TOKEN` | Shared secret of at least 32 characters. Non-loopback callers must send it as `X-Buswise-Token`. |
| api | `ONEMAP_EMAIL`, `ONEMAP_PASSWORD` | Optional live OneMap routing. The API signs in and renews the 3-day token automatically. |
| api | `ONEMAP_TOKEN` | Alternative to the above: a token you fetched yourself (expires after 3 days) |
| api | `OLLAMA_URL` | Ollama endpoint (default `http://127.0.0.1:11434`) |
| api, web, gateway | `PORT` | Listen port (defaults 8765 / 3000 / 8080) |
| gateway | `API_URL`, `WEB_URL` | Upstream URLs |
| gateway | `BUSWISE_API_TOKEN` | Must match the API's token |
| gateway | `RATE_LIMIT_PER_MINUTE` | Per-IP limit on `/api` (default 60) |
| gateway | `CHAT_RATE_LIMIT_PER_MINUTE` | Per-IP limit on `/api/chat` (default 20) |
| gateway | `GLOBAL_RATE_LIMIT_PER_MINUTE` | Per-IP limit on all routes (default 300) |
| gateway | `TRUST_PROXY` | Number of trusted proxy hops in front. Set it to `1` on Cloud Run, Render or behind a load balancer. Leave it unset otherwise, or clients could fake their IP. |
| gateway | `ALLOWED_ORIGINS` | Comma-separated extra origins allowed to call `/api` from a browser (default: none) |
