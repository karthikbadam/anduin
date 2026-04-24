# syntax=docker/dockerfile:1.7

# ─── build stage ────────────────────────────────────────────────────
FROM node:20-alpine AS build
WORKDIR /app
RUN corepack enable && corepack prepare pnpm@9 --activate

COPY package.json pnpm-lock.yaml* ./
# We don't ship a lockfile yet; first build will resolve fresh.
RUN pnpm install --no-frozen-lockfile

COPY tsconfig.json vite.config.ts index.html ./
COPY src ./src
RUN pnpm build

# ─── dev stage (used by docker-compose.override.yml) ────────────────
FROM node:20-alpine AS dev
WORKDIR /app
RUN corepack enable && corepack prepare pnpm@9 --activate
COPY package.json pnpm-lock.yaml* ./
RUN pnpm install --no-frozen-lockfile
COPY . .
EXPOSE 5173
CMD ["pnpm", "dev", "--host"]

# ─── prod stage ─────────────────────────────────────────────────────
FROM nginx:1.27-alpine AS prod
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY docker-entrypoint.d/10-envsubst.sh /docker-entrypoint.d/10-envsubst.sh
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
