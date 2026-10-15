FROM nginx:alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY . /usr/share/nginx/html

# Health endpoint required by Coolify healthchecks
RUN printf '{"status":"ok"}' > /usr/share/nginx/html/health.json

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD wget -qO- http://localhost/health.json || exit 1

EXPOSE 80
