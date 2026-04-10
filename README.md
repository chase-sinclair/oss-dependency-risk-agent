# OSS Dependency Risk Agent

The OSS Dependency Risk Agent is an autonomous monitoring system that tracks the health of 200+ open source dependencies by continuously ingesting GitHub Archive event data into an AWS S3 bronze layer, processing and enriching it through a Databricks/PySpark silver layer, and modeling health metrics in a dbt gold layer — then feeding those signals into a LangGraph agent powered by Anthropic Claude to automatically generate structured risk assessments, surface deteriorating projects, and present findings through a Streamlit dashboard backed by Pinecone vector search.

## Architecture Diagram

> _Diagram coming soon._
>
> <!-- Replace this comment with an architecture image once finalized:
>      ![Architecture](docs/architecture.png) -->

## Project Structure

```
oss-dependency-risk-agent/
├── ingestion/                  # Bronze layer — GH Archive download & S3 upload
│   ├── github_archive/         # Hourly dump fetchers
│   └── utils/                  # Shared ingestion helpers
├── transformation/
│   ├── databricks/             # Silver layer — PySpark notebooks & jobs
│   │   ├── notebooks/
│   │   └── jobs/
│   └── dbt/                    # Gold layer — health metric models
│       ├── models/
│       │   ├── staging/
│       │   ├── intermediate/
│       │   └── gold/
│       ├── tests/
│       ├── macros/
│       └── seeds/
├── agent/                      # LangGraph agent orchestration
│   ├── tools/                  # Agent tool definitions
│   ├── nodes/                  # Graph node implementations
│   ├── graphs/                 # LangGraph graph definitions
│   └── prompts/                # Prompt templates
├── embeddings/                 # Pinecone index management & upsert logic
├── frontend/                   # Streamlit dashboard
│   ├── pages/
│   └── components/
├── config/                     # App-level configuration objects
├── tests/
│   ├── unit/
│   └── integration/
├── docs/                       # Architecture diagrams, ADRs
└── scripts/                    # One-off ops scripts
```

## Quickstart

```bash
# 1. Clone and enter the repo
git clone <repo-url>
cd oss-dependency-risk-agent

# 2. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
# Edit .env with your API keys and connection strings

# 5. Run the Streamlit frontend
streamlit run frontend/app.py
```

## Tech Stack

| Layer | Technology |
|---|---|
| Raw storage | AWS S3 |
| Data processing | Databricks + PySpark |
| Metric modeling | dbt (dbt-databricks) |
| Agent orchestration | LangGraph |
| LLM | Anthropic Claude |
| Vector search | Pinecone |
| Frontend | Streamlit |
| Language | Python 3.13 |
