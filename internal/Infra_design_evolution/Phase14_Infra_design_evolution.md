# Phase 14 — Infrastructure Design Evolution

> **Purpose:** Explain how CloudDesk's infrastructure evolved in Phase 14 — from a developer laptop to a fully containerised, cloud-deployable platform. Each section shows the wiring and routing with diagrams and plain-English explanations.

---

## Baseline: Where We Were Before Phase 14

Before Phase 14, the entire platform ran on a developer's laptop with no containers, no cloud, and simulated services:

```mermaid
graph LR
    DEV[Developer Laptop]
    subgraph proc["Single OS Process"]
        FA[FastAPI :8000\nPython process]
        NX[Next.js :3000\nNode.js process]
    end
    subgraph fake["Simulated services"]
        FR[fakeredis\nin-memory Python object]
        SQ[SQLite\nfile on disk]
        MV[InMemoryVectorStore\nPython dict]
    end

    DEV --> FA
    DEV --> NX
    FA --> FR
    FA --> SQ
    FA --> MV

    style proc fill:#fff9c4,stroke:#f9a825
    style fake fill:#fce4ec,stroke:#880e4f
```

**Problem:** Works only on this exact machine with this exact Python/Node version. Cannot be shipped to anyone else.

---

## Evolution 1 — Multi-Stage Docker Builds (P14-2)

### What Changed

We wrapped each service in its own Docker image. The build process has two stages, like baking a cake vs. serving it:

```mermaid
graph TD
    subgraph backend_dockerfile["backend/Dockerfile"]
        direction TB
        B1["Stage 1: Builder\nFROM python:3.12-slim\n• Install uv\n• uv sync (all deps)\n• Output: /app/deps"]
        B2["Stage 2: Runtime\nFROM python:3.12-slim\n• COPY deps from builder\n• COPY source code\n• RUN useradd app\n• USER app\n• EXPOSE 8000\n• HEALTHCHECK /health/live"]
        B1 -->|only runtime deps copied| B2
    end

    subgraph frontend_dockerfile["frontend/Dockerfile"]
        direction TB
        F1["Stage 1: Deps\nFROM node:22-alpine\n• npm ci"]
        F2["Stage 2: Builder\nFROM node:22-alpine\n• COPY node_modules\n• ARG NEXT_PUBLIC_API_URL\n• npm run build\n• Output: .next/standalone"]
        F3["Stage 3: Runtime\nFROM node:22-alpine\n• COPY standalone output\n• RUN adduser app\n• USER app\n• EXPOSE 3000\n• HEALTHCHECK /api/health"]
        F1 --> F2
        F2 -->|only standalone output| F3
    end

    B2 -->|docker push| REG1[Registry\nbackend:git-sha]
    F3 -->|docker push| REG2[Registry\nfrontend:git-sha]

    style backend_dockerfile fill:#e3f2fd,stroke:#1565c0
    style frontend_dockerfile fill:#fce4ec,stroke:#c62828
```

### Why Multi-Stage?

| Stage | Contains | Size |
|---|---|---|
| Builder | Compiler, uv, all dev packages | Large (~800MB) |
| Runtime | Only the installed packages needed to run | Small (~200MB) |

The build stage is **thrown away** — only the runtime stage gets shipped. This means attackers cannot use build tools inside a running container.

### Why Non-Root?

```mermaid
graph LR
    A[Container starts] --> B{Who is running the process?}
    B -->|root UID 0| C[If container escapes:\nattacker has root on host]
    B -->|app UID 1001| D[If container escapes:\nattacker has very limited permissions]
    style C fill:#ffcdd2,stroke:#c62828
    style D fill:#c8e6c9,stroke:#2e7d32
```

---

## Evolution 2 — Docker Compose Local Stack (P14-3)

### Full Stack Component Wiring

```mermaid
graph TD
    subgraph host["Developer Machine / CI Server"]
        subgraph net["clouddesk bridge network\n(containers communicate by service name)"]

            subgraph tier1["Tier 1 — Data stores\n(start first)"]
                R["redis:7.4-alpine\nContainer: clouddesk_redis_1\nInternal port: 6379\nExternal: none\nVolume: redis_data:/data\nHealthcheck: redis-cli ping"]
                Q["qdrant:1.12.1\nContainer: clouddesk_qdrant_1\nInternal port: 6333\nExternal: none\nVolume: qdrant_data:/qdrant/storage\nHealthcheck: wget /healthz"]
            end

            subgraph tier2["Tier 2 — Backend\n(waits for Tier 1 healthy)"]
                B["backend (custom image)\nContainer: clouddesk_backend_1\nInternal: 8000\nExternal: 0.0.0.0:8000\nVolume: backend_data:/app/data\nREDIS_URL=redis://redis:6379/0\nQDRANT_URL=http://qdrant:6333\nHealthcheck: /health/live"]
            end

            subgraph tier3["Tier 3 — Frontend\n(waits for Backend healthy)"]
                F["frontend (custom image)\nContainer: clouddesk_frontend_1\nInternal: 3000\nExternal: 0.0.0.0:3000\nNEXT_PUBLIC_API_URL=http://backend:8000\nHealthcheck: /api/health"]
            end

            R -->|service_healthy| B
            Q -->|service_healthy| B
            B -->|service_healthy| F
        end
    end

    BROWSER[Browser\nhttp://localhost:3000] -->|HTTP| F
    CURL[curl / API client\nhttp://localhost:8000] -->|HTTP| B

    style tier1 fill:#fff9c4,stroke:#f9a825
    style tier2 fill:#e3f2fd,stroke:#1565c0
    style tier3 fill:#fce4ec,stroke:#c62828
    style net fill:#f5f5f5,stroke:#9e9e9e
```

### Startup Sequence

```mermaid
sequenceDiagram
    participant D as docker compose up
    participant R as Redis
    participant Q as Qdrant
    participant B as Backend
    participant F as Frontend

    D->>R: Start redis container
    D->>Q: Start qdrant container
    R->>D: Health: PASS (redis-cli ping)
    Q->>D: Health: PASS (wget /healthz)
    D->>B: Start backend (Tier 1 healthy)
    B->>R: Connect REDIS_URL
    B->>Q: Connect QDRANT_URL
    B->>D: Health: PASS (/health/live)
    D->>F: Start frontend (Backend healthy)
    F->>B: API calls (http://backend:8000)
    F->>D: Health: PASS (/api/health)
    D-->>D: All services healthy
```

### Volume Layout

```mermaid
graph LR
    subgraph named_volumes["Named Docker Volumes"]
        V1[redis_data\nRedis RDB snapshots]
        V2[qdrant_data\nVector index files]
        V3[backend_data\nSQLite DB + checkpoint DB]
    end

    subgraph containers["Containers"]
        R[Redis container] --> V1
        Q[Qdrant container] --> V2
        B[Backend container] --> V3
    end

    NOTE[docker compose down\ndoes NOT delete volumes\n\ndocker compose down -v\ndeletes volumes]
    style NOTE fill:#fff9c4,stroke:#f9a825
```

---

## Evolution 3 — Cloud Infrastructure (P14-4)

### Three-Cloud Architecture Overview

```mermaid
graph TD
    subgraph aws_arch["AWS Architecture"]
        ECR[ECR\nContainer Registry]
        ECS[ECS Fargate\nServerless containers]
        ALB[ALB\nApplication Load Balancer]
        EC[ElastiCache\nRedis]
        SM[Secrets Manager]
        CW[CloudWatch\nLogs + Alerts]
        ECR -->|image pull| ECS
        ECS --> EC
        ECS --> SM
        ALB --> ECS
        ECS --> CW
    end

    subgraph azure_arch["Azure Architecture"]
        ACR[ACR\nContainer Registry]
        ACA[Container Apps\nServerless containers]
        AALB[Azure Load Balancer]
        ARC[Azure Cache for Redis]
        AKV[Key Vault]
        ALA[Log Analytics]
        ACR -->|image pull| ACA
        ACA --> ARC
        ACA --> AKV
        AALB --> ACA
        ACA --> ALA
    end

    subgraph gcp_arch["GCP Architecture"]
        AR[Artifact Registry\nContainer Registry]
        CR[Cloud Run\nServerless containers]
        GCLB[Cloud Load Balancing]
        GMS[Memorystore\nRedis]
        GSM[Secret Manager]
        GCL[Cloud Logging]
        AR -->|image pull| CR
        CR --> GMS
        CR --> GSM
        GCLB --> CR
        CR --> GCL
    end

    USERS[Users\nHTTPS] --> ALB
    USERS --> AALB
    USERS --> GCLB

    QD[Qdrant Cloud\nexternal - all clouds]
    SB[Supabase\nexternal - all clouds]
    LLMAPI[LLM API\nexternal - all clouds]

    ECS --> QD
    ACA --> QD
    CR --> QD
    ECS --> SB
    ACA --> SB
    CR --> SB

    style aws_arch fill:#fff3e0,stroke:#ef6c00
    style azure_arch fill:#e3f2fd,stroke:#1565c0
    style gcp_arch fill:#e8f5e9,stroke:#2e7d32
```

### Terraform Module Wiring

```mermaid
graph TD
    subgraph roots["Terraform Roots\n(one per cloud)"]
        TF_AWS[deployment/aws/main.tf]
        TF_AZ[deployment/azure/main.tf]
        TF_GCP[deployment/gcp/main.tf]
    end

    subgraph modules["Shared Modules\n(deployment/modules/)"]
        MOD_NET[networking\nVPC + subnets + NAT]
        MOD_REG[container-registry\nECR/ACR/Artifact Registry]
        MOD_SEC[secrets\nSecrets Manager/Key Vault/Secret Manager]
        MOD_RD[redis\nElastiCache/Azure Cache/Memorystore]
        MOD_CM[compute\nECS/Container Apps/Cloud Run]
        MOD_LB[load-balancer\nALB/Azure LB/Cloud LB]
        MOD_MN[monitoring\nCloudWatch/Log Analytics/Cloud Logging]
    end

    TF_AWS --> MOD_NET
    TF_AWS --> MOD_REG
    TF_AWS --> MOD_SEC
    TF_AWS --> MOD_RD
    TF_AWS --> MOD_CM
    TF_AWS --> MOD_LB
    TF_AWS --> MOD_MN

    TF_AZ --> MOD_NET
    TF_AZ --> MOD_REG
    TF_AZ --> MOD_CM
    TF_AZ --> MOD_LB

    TF_GCP --> MOD_NET
    TF_GCP --> MOD_REG
    TF_GCP --> MOD_CM
    TF_GCP --> MOD_LB

    style roots fill:#e8eaf6,stroke:#3f51b5
    style modules fill:#fff3e0,stroke:#ef6c00
```

### Secret Routing (Never in Code)

```mermaid
graph TD
    subgraph safe["Safe Paths for Secrets"]
        ENV_VAR[TF_VAR_jwt_secret\nTF_VAR_db_password\n... set in CI runner environment]
        GH_ENV[GitHub Encrypted Secrets\nstored in GitHub — never in repo]
        CLOUD_SM[Cloud Secret Manager\nAWS Secrets Manager / Azure Key Vault / GCP Secret Manager]
    end

    subgraph app["Running Application"]
        CONTAINER[Container at runtime\nreads from cloud secret manager\nor environment variable injection]
    end

    subgraph never["Never Allowed"]
        TF_FILE[terraform.tfvars\nwith real passwords]
        ENV_FILE[.env\nwith real API keys]
        GIT_REPO[git repository\nsecrets in code]
    end

    ENV_VAR -->|CI injects at plan time| CLOUD_SM
    GH_ENV -->|GitHub Actions injects| ENV_VAR
    CLOUD_SM -->|at deploy time| CONTAINER

    style safe fill:#c8e6c9,stroke:#2e7d32
    style never fill:#ffcdd2,stroke:#c62828
    style app fill:#e3f2fd,stroke:#1565c0
```

---

## Evolution 4 — CI/CD Pipeline Infrastructure (P14-4 continued)

### GitHub Actions Workflow Infrastructure

```mermaid
graph TD
    subgraph github["GitHub Platform"]
        REPO[Code Repository\nmain / development branches]
        GHA[GitHub Actions\nCI runner]
        ENVS[GitHub Environments\ndev, staging, prod, prod-apply]
        SECS[GitHub Secrets\nOIDC role ARNs, cloud credentials]
    end

    subgraph workflows["Workflow Files (.github/workflows/)"]
        T[test.yml\nruff + pytest + npm]
        S[security.yml\ngitleaks + trivy + checkov]
        D[docker-build.yml\nbuild + compose validate]
        TV[terraform-validate.yml\ntf validate × 3]
        DEP[_deploy.yml\nreusable deploy pipeline]
    end

    subgraph cloud_auth["Cloud Authentication (OIDC — no long-lived keys)"]
        AWS_OIDC[AWS OIDC\nIAM Role via AssumeRoleWithWebIdentity]
        AZ_OIDC[Azure OIDC\nWorkload Identity Federation]
        GCP_OIDC[GCP OIDC\nWorkload Identity Provider]
    end

    REPO -->|push event| GHA
    GHA --> T
    GHA --> S
    GHA --> D
    GHA --> TV
    GHA --> DEP

    DEP --> AWS_OIDC
    DEP --> AZ_OIDC
    DEP --> GCP_OIDC

    ENVS -->|prod-apply: required reviewers| DEP
    SECS -->|injected at runtime| DEP

    style github fill:#f5f5f5,stroke:#9e9e9e
    style workflows fill:#e8eaf6,stroke:#3f51b5
    style cloud_auth fill:#e8f5e9,stroke:#2e7d32
```

### Deploy Pipeline Routing

```mermaid
flowchart TD
    START[CI: all checks pass] --> BP[build_and_push.sh\nimage_tag = git SHA]
    BP --> TFP[terraform plan\n-var-file=environments/ENV/terraform.tfvars]

    TFP --> BRANCH{Which environment?}

    BRANCH -->|dev| AUTO[terraform apply\nauto-approved]
    BRANCH -->|staging| WAIT_STG[Human reviews plan\nCI pauses]
    BRANCH -->|prod| WAIT_PRD[GitHub Environment: prod-apply\nRequired reviewer must approve\nCI pauses until approved]

    WAIT_STG -->|approved| APPLY_STG[terraform apply]
    WAIT_PRD -->|approved| APPLY_PRD[terraform apply]

    AUTO --> SMOKE1[smoke_test.sh]
    APPLY_STG --> SMOKE2[smoke_test.sh]
    APPLY_PRD --> SMOKE3[smoke_test.sh]

    SMOKE1 --> END1[Deploy complete]
    SMOKE2 --> END2[Deploy complete]
    SMOKE3 --> END3[Deploy complete]

    style WAIT_PRD fill:#fff9c4,stroke:#f9a825
    style WAIT_STG fill:#fff9c4,stroke:#f9a825
    style AUTO fill:#c8e6c9,stroke:#2e7d32
```

---

## Evolution 5 — Kubernetes Manifests (P14-4)

For organisations that run Kubernetes instead of managed container services:

```mermaid
graph TD
    subgraph k8s["Kubernetes Cluster"]
        subgraph ns["Namespace: clouddesk"]
            subgraph backend_dp["Backend Deployment"]
                BP1[Pod 1\nclouddesk-backend:git-sha\nUSER 1001\nliveness: /health/live\nreadiness: /health/ready\nresources: 250m-1000m CPU\n512Mi-1Gi RAM]
                BP2[Pod 2\n...]
            end
            subgraph frontend_dp["Frontend Deployment"]
                FP1[Pod 1\nclouddesk-frontend:git-sha\nUSER 1001\nliveness: /api/health\nresources: 100m-500m CPU\n256Mi-512Mi RAM]
                FP2[Pod 2\n...]
            end
            BSvc[Service: clouddesk-backend\nClusterIP :8000]
            FSvc[Service: clouddesk-frontend\nClusterIP :3000]
        end

        INGRESS[Ingress Controller\nTLS termination\nrouting rules]
    end

    BP1 --> BSvc
    BP2 --> BSvc
    FP1 --> FSvc
    FP2 --> FSvc
    INGRESS --> BSvc
    INGRESS --> FSvc

    USERS[Users\nhttps://] --> INGRESS

    style k8s fill:#e3f2fd,stroke:#1565c0
    style ns fill:#bbdefb,stroke:#1565c0
    style INGRESS fill:#fff3e0,stroke:#ef6c00
```

---

## Final State — Complete Infrastructure Picture

```mermaid
graph TD
    subgraph dev_env["Development Environment"]
        LAPTOP[Developer Laptop\nmake backend / npm dev]
        DC[docker compose up --build\nAll 4 services, local volumes]
    end

    subgraph ci_env["CI Environment (GitHub Actions)"]
        CI[GitHub Actions Runner\ntest + security + docker-build + tf-validate]
        REGISTRY[Container Registry\nbackend:git-sha\nfrontend:git-sha]
    end

    subgraph cloud_env["Production Cloud (pick one)"]
        subgraph aws_prod["AWS"]
            ALBUS[ALB]
            ECSP[ECS Fargate\n2 tasks backend\n2 tasks frontend]
            RDSP[ElastiCache Redis]
        end
        subgraph ext["External Services (all clouds)"]
            SUP[Supabase\nPostgreSQL]
            QDC[Qdrant Cloud\nVector Store]
            LLMP[LLM API\nOpenAI / Anthropic]
        end
    end

    LAPTOP -->|code push| CI
    CI -->|build + push| REGISTRY
    REGISTRY -->|deploy| ECSP
    ECSP --> RDSP
    ECSP --> SUP
    ECSP --> QDC
    ECSP --> LLMP
    ALBUS --> ECSP

    style dev_env fill:#fff9c4,stroke:#f9a825
    style ci_env fill:#e3f2fd,stroke:#1565c0
    style cloud_env fill:#e8f5e9,stroke:#2e7d32
    style ext fill:#f3e5f5,stroke:#4a148c
```

---

## Networking Summary Table

| Component | Protocol | From → To | Port | Auth |
|---|---|---|---|---|
| Browser → Frontend | HTTPS | Internet → Load Balancer | 443 | none (public) |
| Load Balancer → Frontend | HTTP | LB → Container | 3000 | none (internal) |
| Frontend → Backend | HTTPS/HTTP | Container → Container | 8000 | Bearer JWT |
| Backend → Redis | Redis | Container → Redis | 6379 | password |
| Backend → Qdrant | HTTP | Container → Qdrant | 6333 | API key |
| Backend → PostgreSQL | TCP | Container → DB | 5432 | connection string |
| Backend → LLM API | HTTPS | Container → External | 443 | API key |
| CI → Cloud Registry | HTTPS | GitHub Actions → Registry | 443 | OIDC token |
| Terraform → Cloud APIs | HTTPS | CI runner → Cloud | 443 | OIDC role |

---

## Honest Status at End of Phase 14

| Item | Status |
|---|---|
| Docker images build locally | ✅ Verified |
| `docker compose up --build` runs | ✅ Verified |
| All 419 tests pass | ✅ Verified |
| Terraform files are syntactically valid | ✅ Verified locally (`terraform validate`) |
| CI workflows created | ✅ Files committed |
| Cloud deployed (AWS / Azure / GCP) | ❌ No cloud credentials configured |
| CI pipelines executed on GitHub | ❌ Needs secrets configured in GitHub |
