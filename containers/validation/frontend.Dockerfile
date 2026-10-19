FROM node:22.23.2-bookworm-slim@sha256:43aeff40f4afc22e83f7589a2f37e111cff5ca84529571f1c8415bcc5fcc21b2 AS dependencies
# Cache the pinned package manager independently of workspace inputs. Bound each
# download attempt so a stalled registry connection cannot hold the whole build.
RUN corepack enable \
    && for attempt in 1 2 3; do \
         timeout --kill-after=5 45 corepack prepare pnpm@10.33.4 --activate && break; \
         if [ "$attempt" -eq 3 ]; then exit 1; fi; \
       done
WORKDIR /build
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY patches/ ./patches/
COPY apps/demo/package.json ./apps/demo/package.json
RUN for attempt in 1 2 3; do \
      timeout --kill-after=5 180 pnpm --config.update-notifier=false \
        --filter @agenthub/demo... install --frozen-lockfile \
        --fetch-timeout=30000 --fetch-retries=2 --reporter=append-only && break; \
      if [ "$attempt" -eq 3 ]; then exit 1; fi; \
    done
# Shared-lockfile deploy creates a frozen, portable subset. The demo has no
# workspace dependencies; enable this strategy only for deploy, keeping the
# original workspace configuration and all patch checks intact.
RUN pnpm --config.update-notifier=false --config.inject-workspace-packages=true \
    --filter @agenthub/demo deploy --offline /runtime

FROM node:22.23.2-bookworm-slim@sha256:43aeff40f4afc22e83f7589a2f37e111cff5ca84529571f1c8415bcc5fcc21b2
ARG AGENTHUB_RECIPE
LABEL io.agenthub.validation.profile="vite-build-smoke-v1" \
      io.agenthub.validation.recipe="${AGENTHUB_RECIPE}"
COPY --from=dependencies /runtime/ /opt/agenthub/apps/demo/
COPY scripts/demo-validation-build.mjs scripts/demo-build-smoke.test.mjs /opt/agenthub/scripts/
COPY --chmod=0555 containers/validation/frontend-control.mjs /opt/agenthub/control
USER 10001:10001
WORKDIR /work
ENTRYPOINT ["/opt/agenthub/control"]
CMD ["hold"]
