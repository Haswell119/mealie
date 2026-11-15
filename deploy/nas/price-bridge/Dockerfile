# Price bridge of Mealie Personal Edition: an HTTP door in front of the swissgroceries MCP server.
#
# The price service is a separate program, under its own license (PolyForm Shield 1.0.0, personal use).
# This repository does not hold its code: `npm install` fetches it here, when you build the image.
# Read its license before you build: https://www.npmjs.com/package/@nicktcode/swissgroceries-mcp

FROM node:22-alpine

# The version is pinned: a new version of the price service is a decision, not a side effect of a build.
ARG PRICE_SERVICE_VERSION=0.12.0

WORKDIR /app
RUN npm install --omit=dev --no-audit --no-fund --ignore-scripts \
        "@nicktcode/swissgroceries-mcp@${PRICE_SERVICE_VERSION}" \
    && npm cache clean --force

COPY bridge.mjs ./

ENV NODE_ENV=production \
    BRIDGE_PORT=8080
USER node
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD wget -q -O /dev/null http://127.0.0.1:8080/health || exit 1

CMD ["node", "bridge.mjs"]
