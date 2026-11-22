# syntax=docker/dockerfile:1
# Frontend Dockerfile — node:22-alpine, standalone output, non-root, HEALTHCHECK on /api/health

# ---------------------------------------------------------------------------
# Stage 1: dependency installer
# ---------------------------------------------------------------------------
FROM node:22-alpine AS deps

WORKDIR /app

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --omit=dev

# ---------------------------------------------------------------------------
# Stage 2: builder
# ---------------------------------------------------------------------------
FROM node:22-alpine AS builder

WORKDIR /app

# Copy deps
COPY --from=deps /app/node_modules ./node_modules
COPY frontend/ .

# Build-time env vars — override via build args per environment
ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL

RUN npm run build

# ---------------------------------------------------------------------------
# Stage 3: runtime — minimal standalone image
# ---------------------------------------------------------------------------
FROM node:22-alpine AS runtime

# Non-root user (§15)
RUN addgroup --gid 1001 app && adduser --uid 1001 --ingroup app --disabled-password --no-create-home app

WORKDIR /app

ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000

# Copy only the standalone output (Next.js standalone mode)
COPY --from=builder --chown=app:app /app/.next/standalone ./
COPY --from=builder --chown=app:app /app/.next/static  ./.next/static
COPY --from=builder --chown=app:app /app/public         ./public

USER app

EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD wget -qO- http://localhost:3000/api/health || exit 1

CMD ["node", "server.js"]
