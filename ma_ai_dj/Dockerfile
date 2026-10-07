# syntax=docker/dockerfile:1
FROM node:24-bookworm AS frontend
RUN apt-get update && apt-get install -y --no-install-recommends python3 \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /build
COPY upstream.json apply.py frontend.patch ./integration/
COPY frontend/ ./integration/frontend/
COPY provider/ ./integration/provider/
RUN git clone https://github.com/music-assistant/server.git server \
    && git clone https://github.com/music-assistant/frontend.git frontend \
    && git -C server checkout $(python3 -c 'import json; print(json.load(open("integration/upstream.json"))["server"])') \
    && git -C frontend checkout $(python3 -c 'import json; print(json.load(open("integration/upstream.json"))["frontend"])') \
    && python3 integration/apply.py --server server --frontend frontend
WORKDIR /build/frontend
ENV NODE_OPTIONS=--max-old-space-size=6144
RUN corepack enable && corepack pnpm install --frozen-lockfile \
    && corepack pnpm exec vue-tsc --noEmit && corepack pnpm exec vite build

FROM ghcr.io/music-assistant/server:2.10.5
COPY provider/ /tmp/ai-dj-provider/
COPY --from=frontend /build/frontend/music_assistant_frontend/ /tmp/ai-dj-frontend/
COPY upstream.json /tmp/ai-dj-upstream.json
COPY install_runtime.py /tmp/ai-dj-install.py
RUN python /tmp/ai-dj-install.py \
    && rm -rf /tmp/ai-dj-provider /tmp/ai-dj-frontend /tmp/ai-dj-upstream.json /tmp/ai-dj-install.py
COPY start.py /app/ai-dj-start.py
ENTRYPOINT ["python", "/app/ai-dj-start.py"]
