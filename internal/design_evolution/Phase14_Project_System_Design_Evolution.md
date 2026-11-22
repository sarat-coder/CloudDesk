# Phase 14 — Project System Design Evolution: Evaluation and Delivery

> **Audience:** Technical reviewers and interview panels who want to understand how the system grew from "it runs on a laptop" to "it can ship to production."

---

## Where We Started at the Beginning of Phase 14

After Phase 13, the CloudDesk platform was functionally complete:
- A working LangGraph AI pipeline that processes support tickets
- A Next.js frontend with a full ticket workflow screen
- Approval and escalation flows
- Memory and observability

But the system had no formal quality proof, no packaging, and no cloud deployment path. The design at the start of Phase 14 looked like this:

### Design 14.0 — Start of Phase 14 (Pre-delivery)

```mermaid
graph TD
    A[Developer Laptop] -->|make backend| B[FastAPI :8000]
    A -->|npm run dev| C[Next.js :3000]
    B --> D[SQLite]
    B --> E[fakeredis]
    B --> F[InMemoryVectorStore]
    B --> G[FakeLLM]

    style A fill:#ffd,stroke:#aa0
    style D fill:#ffa,stroke:#aa0
    style E fill:#ffa,stroke:#aa0
    style F fill:#ffa,stroke:#aa0
    style G fill:#ffa,stroke:#aa0
```

**Gap:** Only runnable on the developer's machine. No quality proof. No production path.

---

## Step 1 — Adding Quality Gates (P14-1)

The first thing we addressed: how do we know the AI is good enough?

We built an evaluation test suite that acts as a **formal quality gate**. The system design didn't change structurally, but we added a measurement layer.

### Design 14.1 — Evaluation Layer Added

```mermaid
graph TD
    subgraph eval["Evaluation Gate (tests/evaluation/)"]
        EC[eval_cases.json\n13 labeled tickets]
        TH[Thresholds\nclassification ≥0.80\nretrieval ≥0.75\nescalation ≥0.90\ncitation ≥0.90\ngrounding ≥0.90]
        EM[test_eval_metrics.py\nautomated pass/fail]
        EC --> EM
        TH --> EM
    end

    subgraph pipeline["AI Pipeline"]
        SA[SupervisorAgent\nclassifies & flags]
        RA[RulesEngine\nescalation policy]
        KA[KnowledgeAgent\nretrieves articles]
        RP[ResolutionAgent\nwrites reply]
    end

    EM --> SA
    EM --> RA
    EM --> KA
    EM --> RP

    style eval fill:#e8f5e9,stroke:#388e3c
    style EC fill:#c8e6c9,stroke:#388e3c
    style TH fill:#c8e6c9,stroke:#388e3c
```

**Key design decision:** Thresholds are code-enforced, not documented aspirations. If classification accuracy drops below 80%, `pytest` fails and the build stops. This turns quality from a manual concern into an automated gate.

**Rules-first principle preserved:** The escalation metric (≥90%) is verified against the **deterministic rules engine**, not the LLM. Policy cases (security breach, GDPR deletion, payment dispute) must escalate 100% of the time — no model probability involved.

---

## Step 2 — Containerising the Application (P14-2)

The next design evolution: wrapping the application in Docker so it runs identically everywhere.

### Design 14.2 — Containerised Components

```mermaid
graph TD
    subgraph backend_img["backend/Dockerfile (multi-stage)"]
        B1[Stage 1: Builder\npython:3.12-slim\ninstall uv + deps] -->|copy deps| B2[Stage 2: Runtime\npython:3.12-slim\nUSER app / HEALTHCHECK]
    end

    subgraph frontend_img["frontend/Dockerfile (multi-stage)"]
        F1[Stage 1: deps\nnode:22-alpine\nnpm ci] --> F2[Stage 2: builder\nnext build]
        F2 -->|copy standalone| F3[Stage 3: runtime\nnode:22-alpine\nUSER app / HEALTHCHECK]
    end

    subgraph code["Repository Root (build context)"]
        SRC1[backend/]
        SRC2[agents/ rag/ memory/ integrations/]
        SRC3[frontend/]
        SRC4[sample_data/]
    end

    SRC1 --> B1
    SRC2 --> B1
    SRC3 --> F1

    B2 -->|image| REG1[Container Registry\nbackend:git-sha]
    F3 -->|image| REG2[Container Registry\nfrontend:git-sha]

    style backend_img fill:#e3f2fd,stroke:#1565c0
    style frontend_img fill:#fce4ec,stroke:#880e4f
    style code fill:#f3e5f5,stroke:#4a148c
```

**Non-root containers:** Both images run as user `app` (UID 1001), not root. This limits blast radius if a container is compromised.

**Multi-stage builds:** The "build" stage installs compilers and dev tools. The "runtime" stage copies only the compiled output. The final image contains nothing that could be used to compile or modify the code — it's a sealed production artifact.

**HEALTHCHECK:** Docker probes the app every 30 seconds. If the probe fails three times, Docker restarts the container automatically, without human intervention.

---

## Step 3 — Composing the Full Stack (P14-3)

With individual containers ready, we needed to wire them together for local development and testing.

### Design 14.3 — Full Stack Compose

```mermaid
graph TD
    subgraph compose["docker-compose.yml"]
        R[redis:7.4-alpine\nhealthcheck: redis-cli ping\nvolume: redis_data]
        Q[qdrant:1.12.1\nhealthcheck: wget /healthz\nvolume: qdrant_data]
        B[backend\nhealthcheck: /health/live\nvolume: backend_data\nports: 8000]
        FR[frontend\nhealthcheck: /api/health\nports: 3000]

        R -->|service_healthy| B
        Q -->|service_healthy| B
        B -->|service_healthy| FR
    end

    NET[clouddesk bridge network\nall services communicate\nby service name]
    compose --- NET

    style R fill:#fff9c4,stroke:#f9a825
    style Q fill:#e1f5fe,stroke:#0288d1
    style B fill:#e8f5e9,stroke:#2e7d32
    style FR fill:#fce4ec,stroke:#c62828
    style NET fill:#f5f5f5,stroke:#9e9e9e
```

**depends_on with health checks:** The compose file uses `condition: service_healthy` for all dependencies. The frontend waits for the backend to pass its health check before starting — this prevents a race condition where the frontend boots before the API is ready.

**Named volumes:** Data persists across `docker compose down` and re-up without needing to re-seed or re-ingest. Only `docker compose down -v` removes the data.

---

## Step 4 — Infrastructure as Code for Three Clouds (P14-4)

The most significant structural expansion: a full Terraform design that lets CloudDesk deploy to any of three major cloud providers with the same codebase.

### Design 14.4a — Terraform Module Architecture

```mermaid
graph TD
    subgraph tf_roots["Terraform Roots"]
        AWS[deployment/aws/main.tf]
        AZ[deployment/azure/main.tf]
        GCP[deployment/gcp/main.tf]
    end

    subgraph modules["Shared Modules (deployment/modules/)"]
        NW[networking\nVPC/VNet/VPC]
        CR[container-registry\nECR/ACR/Artifact Registry]
        SC[secrets\nSecrets Manager/Key Vault/Secret Manager]
        RD[redis\nElastiCache/Azure Cache/Memorystore]
        CM[compute\nECS Fargate/Container Apps/Cloud Run]
        LB[load-balancer\nALB/Azure LB/Cloud LB]
        MN[monitoring\nCloudWatch/Log Analytics/Cloud Logging]
    end

    AWS --> NW
    AWS --> CR
    AWS --> SC
    AWS --> RD
    AWS --> CM
    AWS --> LB
    AWS --> MN

    AZ --> NW
    AZ --> CR
    AZ --> SC
    AZ --> RD
    AZ --> CM
    AZ --> LB
    AZ --> MN

    GCP --> NW
    GCP --> CR
    GCP --> SC
    GCP --> RD
    GCP --> CM
    GCP --> LB
    GCP --> MN

    style tf_roots fill:#e8eaf6,stroke:#3f51b5
    style modules fill:#fff3e0,stroke:#ef6c00
```

### Design 14.4b — Environment Layering

```mermaid
graph LR
    subgraph envs["Variable Files (no secrets)"]
        DEV[environments/dev/terraform.tfvars\nenvironment=dev\nregion=us-east-1]
        STG[environments/staging/terraform.tfvars\nenvironment=staging]
        PRD[environments/prod/terraform.tfvars\nenvironment=prod]
    end

    subgraph ci["CI Pipeline"]
        IMG[image_tag = git SHA\npassed via TF_VAR_image_tag]
        SEC[Secrets via TF_VAR_*\nnever in committed files]
    end

    subgraph tf["Terraform Apply"]
        PLAN[terraform plan\n-var-file=environments/ENV/terraform.tfvars\n-var image_tag=SHA]
        APPLY[terraform apply\nprod requires human approval]
    end

    DEV --> PLAN
    STG --> PLAN
    PRD --> PLAN
    IMG --> PLAN
    SEC --> PLAN
    PLAN --> APPLY

    style envs fill:#e8f5e9,stroke:#2e7d32
    style ci fill:#e3f2fd,stroke:#1565c0
    style tf fill:#fce4ec,stroke:#c62828
```

**Key security rule:** No secrets are ever in committed Terraform files. The image tag, database passwords, API keys, and cloud credentials are all passed via environment variables (`TF_VAR_*`) at deploy time.

**Image tag = git SHA:** The exact same container image that passed CI is what gets deployed. This traceability is a fundamental delivery principle.

---

## Step 5 — CI/CD Pipelines (P14-4 continued)

### Design 14.5 — Full CI/CD Pipeline Flow

```mermaid
graph TD
    subgraph trigger["Git Event"]
        PUSH[Push / PR to main\nor development branch]
    end

    subgraph ci_jobs["Parallel CI Jobs"]
        T[test.yml\nruff + pytest + npm lint/test/build]
        S[security.yml\ngitleaks + pip-audit + trivy + checkov]
        D[docker-build.yml\nbuild images + docker compose config]
        TV[terraform-validate.yml\nterraform init + validate × 3 clouds]
    end

    subgraph deploy["Deploy Pipeline (_deploy.yml)"]
        REG[bootstrap-registry]
        BLD[build-and-push\nimage_tag = git SHA]
        PLN[terraform plan]
        APR{prod?\nrequired reviewers\nprod-apply environment}
        APP[terraform apply]
        SMK[smoke_test.sh\nhealth + auth checks]
    end

    PUSH --> T
    PUSH --> S
    PUSH --> D
    PUSH --> TV

    T -->|all pass| REG
    REG --> BLD
    BLD --> PLN
    PLN --> APR
    APR -->|dev/staging auto| APP
    APR -->|prod: human must approve| APP
    APP --> SMK

    style trigger fill:#f5f5f5,stroke:#9e9e9e
    style ci_jobs fill:#e3f2fd,stroke:#1565c0
    style deploy fill:#e8f5e9,stroke:#2e7d32
    style APR fill:#fff9c4,stroke:#f9a825
```

---

## Step 6 — Deployment Hygiene Tests (P14-5)

The final piece: automated tests that verify the delivery files themselves are correct.

### Design 14.6 — Full System with Quality Gates

```mermaid
graph TD
    subgraph code_changes["Code Changes (PR)"]
        PR[Pull Request\nto development or main]
    end

    subgraph gates["Automated Quality Gates"]
        UNIT[419 unit + integration tests\npytest + vitest]
        EVAL[Evaluation metrics\n5 AI quality thresholds]
        DEPLOY[Deployment hygiene\nDockerfiles, compose,\n.env.example, Terraform,\nCI workflows, scripts]
        SEC[Security scan\nsecrets, CVEs, IaC]
    end

    subgraph artifacts["Deliverables"]
        IMG_B[backend:git-sha\nnon-root, healthcheck]
        IMG_F[frontend:git-sha\nnon-root, healthcheck]
        COMP[docker-compose.yml\n4 services, health deps]
        TF[Terraform\naws + azure + gcp]
        PIPE[GitHub Actions\n5 CI workflows]
    end

    PR --> UNIT
    PR --> EVAL
    PR --> DEPLOY
    PR --> SEC

    UNIT -->|pass| IMG_B
    EVAL -->|pass| IMG_B
    DEPLOY -->|pass| IMG_F
    SEC -->|pass| COMP
    UNIT -->|pass| TF
    UNIT -->|pass| PIPE

    style code_changes fill:#f5f5f5,stroke:#9e9e9e
    style gates fill:#e8f5e9,stroke:#2e7d32
    style artifacts fill:#e3f2fd,stroke:#1565c0
```

---

## Final Architecture — End of Phase 14

This is the complete, delivered system:

```mermaid
graph TD
    subgraph users["Users"]
        AGT[Support Agent\nbrowser]
    end

    subgraph lb["Load Balancer\nAWS ALB / Azure LB / GCP Cloud LB"]
        LBD[Routes :443\nto frontend or backend]
    end

    subgraph app["Application Tier"]
        FE[Next.js :3000\nfrontend:git-sha\nnon-root, healthcheck]
        BE[FastAPI :8000\nbackend:git-sha\nnon-root, healthcheck]
    end

    subgraph data["Data Tier"]
        PG[(PostgreSQL\nSupabase / RDS / Azure DB)]
        RD[(Redis\nElastiCache / Azure Cache / Memorystore)]
        QD[(Qdrant\nQdrant Cloud)]
    end

    subgraph ai["AI Tier (inside backend)"]
        LG[LangGraph Workflow]
        LLM[LLM Provider\nopenai / anthropic / fake]
    end

    subgraph obs["Observability"]
        LOG[JSON Logs\nrequest_id, workflow_id]
        EVT[workflow_events\nnode timings, costs]
        LS[LangSmith\noptional]
    end

    subgraph eval["Quality Gate"]
        EV[419 tests\n5 eval metrics]
    end

    AGT -->|HTTPS| LBD
    LBD --> FE
    FE -->|REST / Bearer JWT| BE
    BE --> PG
    BE --> RD
    BE --> QD
    BE --> LG
    LG --> LLM
    BE --> LOG
    BE --> EVT
    EVT --> LS
    EV -->|pass before ship| BE

    style users fill:#f5f5f5,stroke:#9e9e9e
    style lb fill:#fff3e0,stroke:#ef6c00
    style app fill:#e3f2fd,stroke:#1565c0
    style data fill:#e8f5e9,stroke:#2e7d32
    style ai fill:#fce4ec,stroke:#c62828
    style obs fill:#f3e5f5,stroke:#4a148c
    style eval fill:#e8f5e9,stroke:#2e7d32
```

---

## Design Decisions Summary

| Decision | Why |
|---|---|
| Thresholds as code assertions | Quality failures are caught automatically, not discovered in production |
| Multi-stage Docker builds | Small, secure images with no build tools in production |
| Non-root containers | Limits damage if a container is compromised |
| `depends_on: service_healthy` in compose | Prevents startup race conditions |
| Shared Terraform modules | One set of modules serves AWS, Azure, and GCP — no duplication |
| image_tag = git SHA | The tested artifact is the shipped artifact — full traceability |
| --auto-approve refused for staging/prod | Human review is required before any production change |
| prod-apply GitHub Environment | An additional layer of human approval, enforced by GitHub |
| Smoke tests post-deploy | Fast sanity check that proves the deployment actually worked |
| Deployment tests in pytest | The delivery files themselves are tested just like application code |
