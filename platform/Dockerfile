# ─────────────────────────────────────────────────────────────────────────────
# Stage 1: deps — install node_modules (cached layer)
# ─────────────────────────────────────────────────────────────────────────────
FROM node:20-alpine AS deps
RUN apk add --no-cache libc6-compat
WORKDIR /app

COPY package.json package-lock.json* yarn.lock* pnpm-lock.yaml* ./
# Use npm install (not npm ci) to handle missing lockfile gracefully
RUN \
  if [ -f yarn.lock ]; then yarn --frozen-lockfile; \
  elif [ -f pnpm-lock.yaml ]; then corepack enable pnpm && pnpm install --frozen-lockfile; \
  elif [ -f package-lock.json ]; then npm ci; \
  else npm install; \
  fi

# ─────────────────────────────────────────────────────────────────────────────
# Stage 2: builder — generate Prisma client + build Next.js
# ─────────────────────────────────────────────────────────────────────────────
FROM node:20-alpine AS builder
RUN apk add --no-cache libc6-compat openssl
WORKDIR /app

COPY --from=deps /app/node_modules ./node_modules
COPY . .

# Generate Prisma client (required before Next.js build)
RUN npx prisma generate

# Build Next.js standalone output
ENV NEXT_TELEMETRY_DISABLED=1
ENV NODE_ENV=production
# Stub required env vars for build-time only (not persisted in final image)
ARG DATABASE_URL=postgresql://stub:stub@stub:5432/stub
ARG AUTH_SECRET=build-stub-secret-not-used-at-runtime
ARG STRIPE_SECRET_KEY=sk_test_stub
ARG RESEND_API_KEY=re_stub
RUN npm run build

# ─────────────────────────────────────────────────────────────────────────────
# Stage 3: runner — minimal production image
# ─────────────────────────────────────────────────────────────────────────────
FROM node:20-alpine AS runner
RUN apk add --no-cache curl openssl

WORKDIR /app
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
ENV PORT=3000
ENV HOSTNAME=0.0.0.0

RUN addgroup --system --gid 1001 nodejs && \
    adduser  --system --uid 1001 nextjs

# Standalone build — self-contained server
COPY --from=builder /app/public                        ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static    ./.next/static

# Prisma — needed for DB operations at runtime
COPY --from=builder --chown=nextjs:nodejs /app/prisma           ./prisma
COPY --from=builder --chown=nextjs:nodejs /app/node_modules/.prisma  ./node_modules/.prisma
COPY --from=builder --chown=nextjs:nodejs /app/node_modules/@prisma  ./node_modules/@prisma

USER nextjs
EXPOSE 3000

HEALTHCHECK --interval=20s --timeout=8s --start-period=45s --retries=5 \
  CMD curl -fs http://localhost:3000/api/health > /dev/null

CMD ["node", "server.js"]
