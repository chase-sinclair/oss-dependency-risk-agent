"""
Curated list of 200+ OSS projects to monitor for health signals.

Each entry is a dict with keys:
    org         GitHub organization or user
    repo        GitHub repository name
    category    Grouping label for dashboards/filtering
    description One-line human-readable description

Public API:
    get_all_projects()  -> list[Project]
    get_project_set()   -> set[str]   (fast 'org/repo' lookup set)
"""
from typing import TypedDict


class Project(TypedDict):
    org: str
    repo: str
    category: str
    description: str


# ── Data & ML ──────────────────────────────────────────────────────────────────
_DATA_ML: list[Project] = [
    {"org": "apache",              "repo": "airflow",             "category": "data_ml",     "description": "Workflow orchestration platform"},
    {"org": "apache",              "repo": "spark",               "category": "data_ml",     "description": "Unified analytics engine"},
    {"org": "dbt-labs",            "repo": "dbt-core",            "category": "data_ml",     "description": "Data transformation tool"},
    {"org": "apache",              "repo": "kafka",               "category": "data_ml",     "description": "Distributed event streaming platform"},
    {"org": "pytorch",             "repo": "pytorch",             "category": "data_ml",     "description": "Machine learning framework"},
    {"org": "langchain-ai",        "repo": "langchain",           "category": "data_ml",     "description": "LLM application framework"},
    {"org": "mlflow",              "repo": "mlflow",              "category": "data_ml",     "description": "ML lifecycle management"},
    {"org": "apache",              "repo": "flink",               "category": "data_ml",     "description": "Stream processing framework"},
    {"org": "apache",              "repo": "beam",                "category": "data_ml",     "description": "Unified batch and streaming processing"},
    {"org": "dask",                "repo": "dask",                "category": "data_ml",     "description": "Parallel computing library"},
    {"org": "ray-project",         "repo": "ray",                 "category": "data_ml",     "description": "Distributed computing framework"},
    {"org": "apache",              "repo": "hudi",                "category": "data_ml",     "description": "Transactional data lake platform"},
    {"org": "delta-io",            "repo": "delta",               "category": "data_ml",     "description": "Open storage format for lakehouses"},
    {"org": "apache",              "repo": "iceberg",             "category": "data_ml",     "description": "Open table format for analytics"},
    {"org": "great-expectations",  "repo": "great_expectations",  "category": "data_ml",     "description": "Data quality and validation framework"},
    {"org": "feast-dev",           "repo": "feast",               "category": "data_ml",     "description": "Open source feature store"},
    {"org": "tensorflow",          "repo": "tensorflow",          "category": "data_ml",     "description": "End-to-end ML platform"},
    {"org": "scikit-learn",        "repo": "scikit-learn",        "category": "data_ml",     "description": "ML library for Python"},
    {"org": "pandas-dev",          "repo": "pandas",              "category": "data_ml",     "description": "Data analysis and manipulation library"},
    {"org": "numpy",               "repo": "numpy",               "category": "data_ml",     "description": "Fundamental array computing for Python"},
    {"org": "scipy",               "repo": "scipy",               "category": "data_ml",     "description": "Scientific computing for Python"},
    {"org": "matplotlib",          "repo": "matplotlib",          "category": "data_ml",     "description": "2D plotting library"},
    {"org": "prefecthq",           "repo": "prefect",             "category": "data_ml",     "description": "Modern workflow orchestration"},
    {"org": "dagster-io",          "repo": "dagster",             "category": "data_ml",     "description": "Cloud-native data orchestration"},
    {"org": "apache",              "repo": "arrow",               "category": "data_ml",     "description": "Columnar in-memory analytics format"},
    {"org": "duckdb",              "repo": "duckdb",              "category": "data_ml",     "description": "In-process OLAP SQL database"},
    {"org": "pola-rs",             "repo": "polars",              "category": "data_ml",     "description": "Fast DataFrame library"},
    {"org": "xgboost",             "repo": "xgboost",             "category": "data_ml",     "description": "Gradient boosting framework"},
    {"org": "keras-team",          "repo": "keras",               "category": "data_ml",     "description": "Deep learning API"},
    {"org": "apache",              "repo": "hadoop",              "category": "data_ml",     "description": "Distributed storage and processing"},
    {"org": "trinodb",             "repo": "trino",               "category": "data_ml",     "description": "Distributed SQL query engine"},
    {"org": "plotly",              "repo": "plotly.py",           "category": "data_ml",     "description": "Interactive visualization library"},
    {"org": "jupyter",             "repo": "notebook",            "category": "data_ml",     "description": "Classic Jupyter notebook"},
    {"org": "jupyterlab",          "repo": "jupyterlab",          "category": "data_ml",     "description": "Next-gen Jupyter UI"},
    {"org": "optuna",              "repo": "optuna",              "category": "data_ml",     "description": "Hyperparameter optimization framework"},
    {"org": "pycaret",             "repo": "pycaret",             "category": "data_ml",     "description": "Low-code ML library"},
]

# ── AI / LLM Tooling ──────────────────────────────────────────────────────────
_AI_LLM: list[Project] = [
    {"org": "langchain-ai",   "repo": "langgraph",             "category": "ai_llm",  "description": "Agent graph orchestration framework"},
    {"org": "run-llama",      "repo": "llama_index",           "category": "ai_llm",  "description": "LLM data framework"},
    {"org": "huggingface",    "repo": "transformers",          "category": "ai_llm",  "description": "State-of-the-art ML models"},
    {"org": "openai",         "repo": "openai-python",         "category": "ai_llm",  "description": "OpenAI Python SDK"},
    {"org": "anthropics",     "repo": "anthropic-sdk-python",  "category": "ai_llm",  "description": "Anthropic Python SDK"},
    {"org": "ollama",         "repo": "ollama",                "category": "ai_llm",  "description": "Run LLMs locally"},
    {"org": "ggerganov",      "repo": "llama.cpp",             "category": "ai_llm",  "description": "LLM inference in C++"},
    {"org": "vllm-project",   "repo": "vllm",                  "category": "ai_llm",  "description": "High-throughput LLM serving engine"},
    {"org": "chroma-core",    "repo": "chroma",                "category": "ai_llm",  "description": "AI-native vector database"},
    {"org": "qdrant",         "repo": "qdrant",                "category": "ai_llm",  "description": "Vector similarity search engine"},
    {"org": "milvus-io",      "repo": "milvus",                "category": "ai_llm",  "description": "Cloud-native vector database"},
    {"org": "weaviate",       "repo": "weaviate",              "category": "ai_llm",  "description": "AI-native vector database"},
    {"org": "microsoft",      "repo": "autogen",               "category": "ai_llm",  "description": "Multi-agent conversation framework"},
    {"org": "crewAIInc",      "repo": "crewAI",                "category": "ai_llm",  "description": "AI agent role-playing framework"},
    {"org": "deepset-ai",     "repo": "haystack",              "category": "ai_llm",  "description": "LLM orchestration framework"},
    {"org": "BerriAI",        "repo": "litellm",               "category": "ai_llm",  "description": "Universal LLM proxy and SDK"},
    {"org": "microsoft",      "repo": "promptflow",            "category": "ai_llm",  "description": "LLM application development toolkit"},
    {"org": "microsoft",      "repo": "semantic-kernel",       "category": "ai_llm",  "description": "AI SDK for Python and .NET"},
    {"org": "unslothai",      "repo": "unsloth",               "category": "ai_llm",  "description": "Faster LLM fine-tuning"},
    {"org": "huggingface",    "repo": "diffusers",             "category": "ai_llm",  "description": "Diffusion model library"},
    {"org": "openai",         "repo": "whisper",               "category": "ai_llm",  "description": "General-purpose speech recognition"},
    {"org": "facebookresearch","repo": "faiss",                "category": "ai_llm",  "description": "Efficient similarity search library"},
    {"org": "nomic-ai",       "repo": "gpt4all",               "category": "ai_llm",  "description": "Run LLMs locally with a UI"},
    {"org": "guidance-ai",    "repo": "guidance",              "category": "ai_llm",  "description": "LLM prompting and control library"},
    {"org": "explosion",      "repo": "spaCy",                 "category": "ai_llm",  "description": "Industrial-strength NLP library"},
    {"org": "huggingface",    "repo": "tokenizers",            "category": "ai_llm",  "description": "Fast state-of-the-art tokenizers"},
    {"org": "lm-sys",         "repo": "FastChat",              "category": "ai_llm",  "description": "Open platform for LLM chatbots"},
    {"org": "skypilot-org",   "repo": "skypilot",              "category": "ai_llm",  "description": "LLM training and serving on any cloud"},
    {"org": "lancedb",        "repo": "lancedb",               "category": "ai_llm",  "description": "Serverless vector database"},
    {"org": "neuml",          "repo": "txtai",                 "category": "ai_llm",  "description": "Semantic search and LLM orchestration"},
]

# ── Infrastructure ─────────────────────────────────────────────────────────────
_INFRASTRUCTURE: list[Project] = [
    {"org": "kubernetes",         "repo": "kubernetes",           "category": "infrastructure", "description": "Container orchestration system"},
    {"org": "hashicorp",          "repo": "terraform",            "category": "infrastructure", "description": "Infrastructure as code tool"},
    {"org": "prometheus",         "repo": "prometheus",           "category": "infrastructure", "description": "Systems monitoring and alerting"},
    {"org": "grafana",            "repo": "grafana",              "category": "infrastructure", "description": "Observability and analytics platform"},
    {"org": "helm",               "repo": "helm",                 "category": "infrastructure", "description": "Kubernetes package manager"},
    {"org": "istio",              "repo": "istio",                "category": "infrastructure", "description": "Service mesh for microservices"},
    {"org": "envoyproxy",         "repo": "envoy",                "category": "infrastructure", "description": "Cloud-native edge and service proxy"},
    {"org": "docker",             "repo": "compose",              "category": "infrastructure", "description": "Multi-container Docker applications"},
    {"org": "containerd",         "repo": "containerd",           "category": "infrastructure", "description": "Industry-standard container runtime"},
    {"org": "open-telemetry",     "repo": "opentelemetry-python", "category": "infrastructure", "description": "Observability framework — Python"},
    {"org": "open-telemetry",     "repo": "opentelemetry-collector","category": "infrastructure","description": "Vendor-agnostic telemetry collector"},
    {"org": "jaegertracing",      "repo": "jaeger",               "category": "infrastructure", "description": "End-to-end distributed tracing"},
    {"org": "argoproj",           "repo": "argo-workflows",       "category": "infrastructure", "description": "Workflow engine for Kubernetes"},
    {"org": "argoproj",           "repo": "argo-cd",              "category": "infrastructure", "description": "GitOps continuous delivery for K8s"},
    {"org": "fluxcd",             "repo": "flux2",                "category": "infrastructure", "description": "GitOps toolkit for Kubernetes"},
    {"org": "cert-manager",       "repo": "cert-manager",         "category": "infrastructure", "description": "K8s certificate management controller"},
    {"org": "cilium",             "repo": "cilium",               "category": "infrastructure", "description": "eBPF-based networking and security"},
    {"org": "crossplane",         "repo": "crossplane",           "category": "infrastructure", "description": "Universal cloud infrastructure control plane"},
    {"org": "open-policy-agent",  "repo": "opa",                  "category": "infrastructure", "description": "General-purpose policy engine"},
    {"org": "falcosecurity",      "repo": "falco",                "category": "infrastructure", "description": "Cloud-native runtime security"},
    {"org": "traefik",            "repo": "traefik",              "category": "infrastructure", "description": "Cloud-native application proxy"},
    {"org": "grpc",               "repo": "grpc",                 "category": "infrastructure", "description": "Universal RPC framework"},
    {"org": "etcd-io",            "repo": "etcd",                 "category": "infrastructure", "description": "Distributed reliable key-value store"},
    {"org": "pulumi",             "repo": "pulumi",               "category": "infrastructure", "description": "Infrastructure as code in any language"},
    {"org": "ansible",            "repo": "ansible",              "category": "infrastructure", "description": "IT automation and configuration management"},
    {"org": "hashicorp",          "repo": "vault",                "category": "infrastructure", "description": "Secrets management and encryption"},
    {"org": "hashicorp",          "repo": "consul",               "category": "infrastructure", "description": "Service mesh and service discovery"},
    {"org": "tektoncd",           "repo": "pipeline",             "category": "infrastructure", "description": "Cloud-native CI/CD pipelines on K8s"},
    {"org": "kedacore",           "repo": "keda",                 "category": "infrastructure", "description": "Kubernetes event-driven autoscaling"},
    {"org": "linkerd",            "repo": "linkerd2",             "category": "infrastructure", "description": "Ultralight service mesh"},
]

# ── Web Frameworks ─────────────────────────────────────────────────────────────
_WEB_FRAMEWORKS: list[Project] = [
    {"org": "tiangolo",    "repo": "fastapi",    "category": "web_frameworks", "description": "Modern, fast Python web framework"},
    {"org": "facebook",    "repo": "react",      "category": "web_frameworks", "description": "JavaScript UI component library"},
    {"org": "pallets",     "repo": "flask",      "category": "web_frameworks", "description": "Lightweight Python web framework"},
    {"org": "django",      "repo": "django",     "category": "web_frameworks", "description": "High-level Python web framework"},
    {"org": "nestjs",      "repo": "nest",       "category": "web_frameworks", "description": "Progressive Node.js server framework"},
    {"org": "expressjs",   "repo": "express",    "category": "web_frameworks", "description": "Minimal Node.js web framework"},
    {"org": "vuejs",       "repo": "vue",        "category": "web_frameworks", "description": "Progressive JavaScript framework"},
    {"org": "angular",     "repo": "angular",    "category": "web_frameworks", "description": "TypeScript-based web application framework"},
    {"org": "sveltejs",    "repo": "svelte",     "category": "web_frameworks", "description": "Compiled JavaScript UI framework"},
    {"org": "vercel",      "repo": "next.js",    "category": "web_frameworks", "description": "React meta-framework"},
    {"org": "vitejs",      "repo": "vite",       "category": "web_frameworks", "description": "Next-generation frontend build tool"},
    {"org": "trpc",        "repo": "trpc",       "category": "web_frameworks", "description": "End-to-end typesafe APIs for TypeScript"},
    {"org": "prisma",      "repo": "prisma",     "category": "web_frameworks", "description": "Next-generation Node.js ORM"},
    {"org": "supabase",    "repo": "supabase",   "category": "web_frameworks", "description": "Open-source Firebase alternative"},
    {"org": "pydantic",    "repo": "pydantic",   "category": "web_frameworks", "description": "Data validation using Python type hints"},
    {"org": "encode",      "repo": "httpx",      "category": "web_frameworks", "description": "Fully featured async HTTP client"},
    {"org": "aio-libs",    "repo": "aiohttp",    "category": "web_frameworks", "description": "Async HTTP client/server framework"},
    {"org": "encode",      "repo": "starlette",  "category": "web_frameworks", "description": "Lightweight ASGI framework"},
    {"org": "tornadoweb",  "repo": "tornado",    "category": "web_frameworks", "description": "Python async web framework"},
    {"org": "sanic-org",   "repo": "sanic",      "category": "web_frameworks", "description": "Async Python web server and framework"},
    {"org": "astro-build", "repo": "astro",      "category": "web_frameworks", "description": "Web framework for content-driven websites"},
    {"org": "remix-run",   "repo": "remix",      "category": "web_frameworks", "description": "Full-stack React web framework"},
]

# ── Databases ─────────────────────────────────────────────────────────────────
_DATABASES: list[Project] = [
    {"org": "redis",         "repo": "redis",          "category": "databases", "description": "In-memory data structure store"},
    {"org": "mongodb",       "repo": "mongo",          "category": "databases", "description": "Document-oriented NoSQL database"},
    {"org": "elastic",       "repo": "elasticsearch",  "category": "databases", "description": "Distributed search and analytics engine"},
    {"org": "ClickHouse",    "repo": "ClickHouse",     "category": "databases", "description": "Column-oriented OLAP database"},
    {"org": "cockroachdb",   "repo": "cockroach",      "category": "databases", "description": "Cloud-native distributed SQL database"},
    {"org": "pingcap",       "repo": "tidb",           "category": "databases", "description": "Distributed HTAP database"},
    {"org": "vitessio",      "repo": "vitess",         "category": "databases", "description": "Database clustering system for MySQL"},
    {"org": "apache",        "repo": "cassandra",      "category": "databases", "description": "Distributed NoSQL database"},
    {"org": "influxdata",    "repo": "influxdb",       "category": "databases", "description": "Time series database"},
    {"org": "timescale",     "repo": "timescaledb",    "category": "databases", "description": "Time series extension for PostgreSQL"},
    {"org": "apache",        "repo": "druid",          "category": "databases", "description": "High-performance real-time analytics DB"},
    {"org": "questdb",       "repo": "questdb",        "category": "databases", "description": "High-performance time series database"},
    {"org": "surrealdb",     "repo": "surrealdb",      "category": "databases", "description": "Multi-model cloud database"},
    {"org": "neon-database", "repo": "neon",           "category": "databases", "description": "Serverless Postgres"},
    {"org": "apache",        "repo": "couchdb",        "category": "databases", "description": "Document-oriented database with REST API"},
    {"org": "redpanda-data", "repo": "redpanda",       "category": "databases", "description": "Kafka-compatible streaming data platform"},
]

# ── Developer Tooling ─────────────────────────────────────────────────────────
_DEV_TOOLING: list[Project] = [
    {"org": "astral-sh",       "repo": "ruff",       "category": "dev_tooling", "description": "Extremely fast Python linter and formatter"},
    {"org": "astral-sh",       "repo": "uv",         "category": "dev_tooling", "description": "Extremely fast Python package manager"},
    {"org": "astral-sh",       "repo": "rye",        "category": "dev_tooling", "description": "Holistic Python project management"},
    {"org": "pypa",            "repo": "pip",        "category": "dev_tooling", "description": "Python package installer"},
    {"org": "python-poetry",   "repo": "poetry",     "category": "dev_tooling", "description": "Python dependency management"},
    {"org": "pre-commit",      "repo": "pre-commit", "category": "dev_tooling", "description": "Multi-language pre-commit hook framework"},
    {"org": "pytest-dev",      "repo": "pytest",     "category": "dev_tooling", "description": "Python testing framework"},
    {"org": "psf",             "repo": "black",      "category": "dev_tooling", "description": "Uncompromising Python code formatter"},
    {"org": "pylint-dev",      "repo": "pylint",     "category": "dev_tooling", "description": "Python static code analysis"},
    {"org": "python",          "repo": "mypy",       "category": "dev_tooling", "description": "Optional static type checker for Python"},
    {"org": "python",          "repo": "cpython",    "category": "dev_tooling", "description": "CPython reference implementation"},
    {"org": "denoland",        "repo": "deno",       "category": "dev_tooling", "description": "Secure JavaScript and TypeScript runtime"},
    {"org": "nodejs",          "repo": "node",       "category": "dev_tooling", "description": "JavaScript runtime built on V8"},
    {"org": "golang",          "repo": "go",         "category": "dev_tooling", "description": "Go programming language"},
    {"org": "rust-lang",       "repo": "rust",       "category": "dev_tooling", "description": "Systems programming language"},
    {"org": "microsoft",       "repo": "vscode",     "category": "dev_tooling", "description": "Code editor"},
    {"org": "cli",             "repo": "cli",        "category": "dev_tooling", "description": "GitHub CLI"},
    {"org": "pypa",            "repo": "setuptools", "category": "dev_tooling", "description": "Python packaging utilities"},
    {"org": "cython",          "repo": "cython",     "category": "dev_tooling", "description": "Optimising static compiler for Python"},
    {"org": "nickel-lang",     "repo": "nickel",     "category": "dev_tooling", "description": "Configuration language"},
]

# ── Security ──────────────────────────────────────────────────────────────────
_SECURITY: list[Project] = [
    {"org": "aquasecurity",   "repo": "trivy",           "category": "security", "description": "Comprehensive vulnerability scanner"},
    {"org": "anchore",        "repo": "grype",           "category": "security", "description": "Container and filesystem vulnerability scanner"},
    {"org": "sigstore",       "repo": "cosign",          "category": "security", "description": "Container signing and verification"},
    {"org": "gitleaks",       "repo": "gitleaks",        "category": "security", "description": "Detect hardcoded secrets in git repos"},
    {"org": "trufflesecurity","repo": "trufflehog",      "category": "security", "description": "Find and verify leaked credentials"},
    {"org": "prowler-cloud",  "repo": "prowler",         "category": "security", "description": "Cloud security and compliance tool"},
    {"org": "bridgecrewio",   "repo": "checkov",         "category": "security", "description": "IaC static analysis security scanner"},
    {"org": "aquasecurity",   "repo": "kube-bench",      "category": "security", "description": "CIS Kubernetes benchmark checker"},
    {"org": "snyk",           "repo": "snyk",            "category": "security", "description": "Developer-first security platform"},
    {"org": "liamg",          "repo": "tfsec",           "category": "security", "description": "Terraform static analysis security scanner"},
    {"org": "oxsecurity",     "repo": "megalinter",      "category": "security", "description": "Multi-language linter and security scanner"},
    {"org": "OWASP",          "repo": "ASVS",            "category": "security", "description": "Application security verification standard"},
]

# ── Observability ─────────────────────────────────────────────────────────────
_OBSERVABILITY: list[Project] = [
    {"org": "grafana",          "repo": "loki",                    "category": "observability", "description": "Like Prometheus but for logs"},
    {"org": "grafana",          "repo": "tempo",                   "category": "observability", "description": "High-scale distributed tracing backend"},
    {"org": "grafana",          "repo": "mimir",                   "category": "observability", "description": "Scalable long-term Prometheus storage"},
    {"org": "vectordotdev",     "repo": "vector",                  "category": "observability", "description": "High-performance observability data pipeline"},
    {"org": "fluent",           "repo": "fluentd",                 "category": "observability", "description": "Open-source data collector"},
    {"org": "elastic",          "repo": "beats",                   "category": "observability", "description": "Lightweight data shippers"},
    {"org": "elastic",          "repo": "kibana",                  "category": "observability", "description": "Visualization dashboard for Elasticsearch"},
    {"org": "netdata",          "repo": "netdata",                 "category": "observability", "description": "Real-time infrastructure monitoring"},
    {"org": "getsentry",        "repo": "sentry",                  "category": "observability", "description": "Application error tracking and performance"},
    {"org": "signoz",           "repo": "signoz",                  "category": "observability", "description": "Open-source APM and observability platform"},
    {"org": "hyperdxio",        "repo": "hyperdx",                 "category": "observability", "description": "Open-source Datadog alternative"},
    {"org": "VictoriaMetrics",  "repo": "VictoriaMetrics",         "category": "observability", "description": "Fast time series database and monitoring"},
]

# ── Messaging & Streaming ─────────────────────────────────────────────────────
_MESSAGING: list[Project] = [
    {"org": "apache",          "repo": "pulsar",            "category": "messaging", "description": "Cloud-native distributed messaging"},
    {"org": "nats-io",         "repo": "nats-server",       "category": "messaging", "description": "High-performance cloud-native messaging"},
    {"org": "rabbitmq",        "repo": "rabbitmq-server",   "category": "messaging", "description": "Multi-protocol messaging broker"},
    {"org": "apache",          "repo": "rocketmq",          "category": "messaging", "description": "Cloud-native messaging and streaming"},
    {"org": "emqx",            "repo": "emqx",              "category": "messaging", "description": "MQTT broker for IoT and real-time messaging"},
    {"org": "celery",          "repo": "celery",            "category": "messaging", "description": "Distributed task queue"},
    {"org": "temporalio",      "repo": "temporal",          "category": "messaging", "description": "Durable execution platform"},
    {"org": "nsqio",           "repo": "nsq",               "category": "messaging", "description": "Realtime distributed messaging platform"},
]

# ── CI / CD ───────────────────────────────────────────────────────────────────
_CICD: list[Project] = [
    {"org": "jenkinsci",    "repo": "jenkins",    "category": "cicd", "description": "Open-source automation server"},
    {"org": "drone",        "repo": "drone",      "category": "cicd", "description": "Container-native CI/CD platform"},
    {"org": "dagger",       "repo": "dagger",     "category": "cicd", "description": "Portable CI/CD pipelines as code"},
    {"org": "earthly",      "repo": "earthly",    "category": "cicd", "description": "Repeatable builds using containers"},
    {"org": "nektos",       "repo": "act",        "category": "cicd", "description": "Run GitHub Actions locally"},
    {"org": "goreleaser",   "repo": "goreleaser", "category": "cicd", "description": "Release automation for Go projects"},
    {"org": "harness",      "repo": "gitness",    "category": "cicd", "description": "Open-source code hosting and CI/CD"},
    {"org": "woodpecker-ci","repo": "woodpecker", "category": "cicd", "description": "Simple CI/CD engine with great extensibility"},
    {"org": "concourse",    "repo": "concourse",  "category": "cicd", "description": "Continuous thing-doer with pipeline-based CI"},
    {"org": "spinnaker",    "repo": "spinnaker",  "category": "cicd", "description": "Multi-cloud continuous delivery platform"},
    {"org": "CircleCI-Public","repo": "circleci-docs","category": "cicd","description": "CircleCI documentation and config reference"},
    {"org": "buildkite",    "repo": "agent",      "category": "cicd", "description": "Open-source build runner for Buildkite"},
    {"org": "go-gitea",     "repo": "gitea",      "category": "cicd", "description": "Lightweight self-hosted Git service"},
    {"org": "gogs",         "repo": "gogs",       "category": "cicd", "description": "Self-hosted Git service in Go"},
]


# ── Discovered (auto-generated) ──
_DISCOVERED: list[Project] = [
    {"org": "fastapi", "repo": "sqlmodel", "category": "discovered", "description": "Discovered from manifest (python package: sqlalchemy)"},
    {"org": "redis", "repo": "redis-py", "category": "discovered", "description": "Discovered from manifest (python package: redis)"},
    {"org": "boto", "repo": "boto3", "category": "discovered", "description": "Discovered from manifest (python package: boto3)"}
]

# ── Master list ───────────────────────────────────────────────────────────────
PROJECTS: list[Project] = (
    _DATA_ML
    + _AI_LLM
    + _INFRASTRUCTURE
    + _WEB_FRAMEWORKS
    + _DATABASES
    + _DEV_TOOLING
    + _SECURITY
    + _OBSERVABILITY
    + _MESSAGING
    + _CICD
    + _DISCOVERED
)


def get_all_projects() -> list[Project]:
    """Return all monitored projects."""
    return PROJECTS


def get_project_set() -> set[str]:
    """Return a set of 'org/repo' strings for O(1) event filtering."""
    return {f"{p['org']}/{p['repo']}" for p in PROJECTS}


def get_projects_by_category(category: str) -> list[Project]:
    """Return projects filtered by category label."""
    return [p for p in PROJECTS if p["category"] == category]


if __name__ == "__main__":
    all_projects = get_all_projects()
    print(f"Total monitored projects: {len(all_projects)}")
    categories: dict[str, int] = {}
    for p in all_projects:
        categories[p["category"]] = categories.get(p["category"], 0) + 1
    for cat, count in sorted(categories.items()):
        print(f"  {cat}: {count}")
