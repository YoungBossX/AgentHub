FROM python:3.12.15-slim-bookworm@sha256:2ed6491b93cd49272ee6de2b5a38440c3448360322c089fc23e370722d74179d
ARG AGENTHUB_RECIPE
LABEL io.agenthub.validation.profile="fastapi-contract-v1" \
      io.agenthub.validation.recipe="${AGENTHUB_RECIPE}"
COPY containers/validation/backend-requirements.lock /opt/agenthub/backend-requirements.lock
RUN python -m pip install --no-cache-dir --disable-pip-version-check --only-binary=:all: \
    --require-hashes -r /opt/agenthub/backend-requirements.lock
COPY scripts/demo-backend-check.py /opt/agenthub/scripts/demo-backend-check.py
COPY --chmod=0555 containers/validation/backend-control.py /opt/agenthub/control
USER 10001:10001
WORKDIR /work
ENTRYPOINT ["/opt/agenthub/control"]
CMD ["hold"]
