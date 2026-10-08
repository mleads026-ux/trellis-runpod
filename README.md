# TRELLIS / RunPod ChatGPT Bridge

Secure Vercel API bridge for controlling RunPod Pods and submitting jobs to a RunPod Serverless endpoint.

## Setup

1. Import this GitHub repository into Vercel as a Node.js project.
2. Configure the following Vercel environment variables:
   - `RUNPOD_API_KEY` — your secret RunPod API key; **never commit it to GitHub**.
   - `ACTION_API_KEY` — a different, long random token used to authenticate calls from ChatGPT.
   - `RUNPOD_POD_ID` — optional existing Pod ID, required for start/stop.
   - `RUNPOD_ENDPOINT_ID` — optional Serverless endpoint ID, required for submit/status.
3. Deploy on Vercel.
4. Test `GET /api/runpod?action=pods` with header `Authorization: Bearer <ACTION_API_KEY>`.
5. Replace `YOUR-VERCEL-DOMAIN` in `openapi.yaml` with the deployed hostname.
6. Add the OpenAPI specification as an Action on a custom GPT, selecting API Key authentication with Bearer scheme and using `ACTION_API_KEY` (never RunPod's key).
7. Treat start/stop and submission as billable actions; ask for approval before triggering paid GPU work.

## Endpoints

- `GET /api/runpod?action=pods` — list current Pods.
- `POST /api/runpod` with `{"action":"start_pod"}` — start the configured Pod.
- `POST /api/runpod` with `{"action":"stop_pod"}` — stop the configured Pod.
- `POST /api/runpod` with `{"action":"submit_job","input":{...}}` — submit to the configured Serverless endpoint.
- `GET /api/runpod?action=job_status&job_id=...` — check a submitted job.

**Important:** This bridge alone does not install TRELLIS, deploy a GPU, or create a Serverless endpoint. The TRELLIS handler/container needs to be deployed on RunPod separately. Its accepted input fields depend on that handler.

**Cost warning:** Stopped Pods may still incur storage charges. Serverless requests can incur charges. Do not put either key in chat messages, GitHub, or client-side JavaScript.
