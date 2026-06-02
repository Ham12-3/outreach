# SETUP

Exact steps to run the Outreach Operations Agent locally and to deploy it to
Cloud Run.

---

## 0. Prerequisites

- **Python 3.10+** (tested on 3.13)
- **Node.js 18+** — the MongoDB MCP server runs via `npx`. Check: `node --version`
- **Google Cloud CLI** (`gcloud`) — for Vertex AI auth and Cloud Run
- A **MongoDB Atlas** cluster + connection string
- A **Google Cloud project** with the Gemini Enterprise Agent Platform / Vertex AI
  API enabled and billing on

---

## 1. Get the code & install

```bash
cd outreach
python -m venv .venv

# activate the venv:
#   Windows (PowerShell):  .venv\Scripts\Activate.ps1
#   macOS/Linux:           source .venv/bin/activate

pip install -r requirements.txt
```

---

## 2. Configure your `.env`

```bash
cp .env.example .env
```

Open `.env` and fill in:

| Variable | What to put |
|---|---|
| `MDB_MCP_CONNECTION_STRING` | Your Atlas connection string **including the password**, e.g. `mongodb+srv://user:pass@cluster0.xxxxx.mongodb.net/?retryWrites=true&w=majority` |
| `MONGODB_DATABASE` | `outreach` (or your choice) |
| `MONGODB_COLLECTION` | `leads` (or your choice) |
| `GOOGLE_GENAI_USE_VERTEXAI` | `TRUE` |
| `GOOGLE_CLOUD_PROJECT` | your GCP project ID |
| `GOOGLE_CLOUD_LOCATION` | e.g. `us-central1` |
| `GEMINI_MODEL` | `gemini-3.1-pro-preview` (already the default) |

**In MongoDB Atlas**, also make sure:
- **Network Access** includes your current IP (or `0.0.0.0/0` for a quick demo).
- The database user in the connection string has **read/write** permission.

> Prefer an AI Studio API key over Vertex AI? Set
> `GOOGLE_GENAI_USE_VERTEXAI=FALSE` and add `GOOGLE_API_KEY=...` to `.env`. Then
> you can skip step 3.

---

## 3. Authenticate to Vertex AI (one time)

```bash
gcloud auth application-default login
gcloud config set project YOUR_PROJECT_ID
```

This creates Application Default Credentials that ADK/Gemini use automatically —
no API key in the code.

---

## 4. Run it

```bash
python main.py
```

You should see the banner with your resolved settings, then a `You:` prompt.
Try:

> Find product managers at US AI startups, store them, score them, draft a
> message for each, and mark them as queued.

The agent will:
1. Load the seed leads (offline).
2. Summarise the insert and ask you to confirm → type `y`.
3. Score each lead and update them (confirm again).
4. Draft messages and update (confirm).
5. Set status to `queued` (confirm).

Read commands (like *"show me all Hot leads"*) run without a confirmation prompt.

### Verify the data landed in MongoDB

In `mongosh` or Atlas Data Explorer:

```js
use outreach
db.leads.find({ segment: "Hot" }).limit(3)
```

### Optional: run via the ADK tooling instead of `main.py`

Because the package exposes `root_agent`, you can also use ADK's built-ins from
the project root:

```bash
adk run outreach_agent     # terminal chat
adk web                    # local web UI at http://localhost:8000
```

> Note: the y/n write confirmation is implemented for the **CLI** (`main.py` /
> `adk run`). In `adk web` and in the Cloud Run server there's no terminal
> stdin, so the gate safely **auto-cancels writes** (fails closed). For a
> server/UI deployment you'd swap the `input()` in `outreach_agent/confirmation.py`
> for an approval step in your UI.

---

## 5. Test the core logic

```bash
pytest
```

9 offline tests cover scoring, drafting, seed loading, and the write-gate
classifier. No MongoDB or Gemini needed.

---

## 6. Deploy to Cloud Run

The agent needs **both Python and Node** at runtime (Node for the MongoDB MCP
server), so we ship a custom `Dockerfile`.

### 6a. Enable APIs (one time)

```bash
gcloud services enable run.googleapis.com aiplatform.googleapis.com \
  artifactregistry.googleapis.com cloudbuild.googleapis.com
```

### 6b. Deploy

From the project root:

```bash
gcloud run deploy outreach-agent \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars "GOOGLE_GENAI_USE_VERTEXAI=TRUE,GOOGLE_CLOUD_PROJECT=YOUR_PROJECT_ID,GOOGLE_CLOUD_LOCATION=us-central1,GEMINI_MODEL=gemini-3.1-pro-preview,MONGODB_DATABASE=outreach,MONGODB_COLLECTION=leads"
```

Then set the secret connection string (kept out of the command history via Secret
Manager is best; the quick path is):

```bash
gcloud run services update outreach-agent --region us-central1 \
  --set-env-vars "MDB_MCP_CONNECTION_STRING=mongodb+srv://user:pass@cluster0.xxxxx.mongodb.net/?retryWrites=true&w=majority"
```

> **Recommended:** store the connection string in **Secret Manager** and mount it
> instead:
> ```bash
> echo -n "mongodb+srv://..." | gcloud secrets create mdb-conn --data-file=-
> gcloud run services update outreach-agent --region us-central1 \
>   --update-secrets "MDB_MCP_CONNECTION_STRING=mdb-conn:latest"
> ```

Cloud Run gives the service the right Vertex AI permissions through its service
account; make sure that account has the **Vertex AI User** role.

The deployed container serves the agent's web UI (`adk web`) on the Cloud Run
URL. Remember the write-gate note in step 4: server deployments fail closed on
writes by default.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `MDB_MCP_CONNECTION_STRING is empty` warning | Fill it in `.env` (or env vars). |
| MongoDB tools time out / auth error | Check Atlas Network Access (IP allowlist) and that the user has read/write. |
| `npx` not found | Install Node.js 18+ and reopen your shell. |
| Gemini auth error | Re-run `gcloud auth application-default login`; confirm `GOOGLE_CLOUD_PROJECT` and that Vertex AI is enabled. |
| Model not found | Confirm `GEMINI_MODEL` is a model available in your project/region. |
| Writes always cancel in `adk web`/Cloud Run | Expected — the y/n gate needs a terminal. Use `python main.py` for the interactive demo. |
