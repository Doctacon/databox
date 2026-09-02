FROM registry.access.redhat.com/ubi9/nodejs-22-minimal:1-1779828907 AS builder
USER root
RUN microdnf install -y git && microdnf clean all
WORKDIR /src
RUN git clone https://github.com/apache/polaris-tools.git . \
    && git checkout 36090e045b9281d8ae837e50b36018bb9913be8a
WORKDIR /src/console
RUN npm install && npm run build

FROM registry.access.redhat.com/ubi9/nginx-126:1-1779858291
USER root
RUN groupadd --gid 10001 polaris && useradd --uid 10000 --gid polaris polaris
COPY --from=builder /src/console/LICENSE-BUNDLE /LICENSE
COPY --from=builder /src/console/NOTICE /NOTICE
COPY --from=builder /src/console/docker/nginx.conf /opt/app-root/etc/nginx.default.d/default.conf
COPY --from=builder /src/console/docker/generate-config.sh /generate-config.sh
COPY --from=builder /src/console/dist /opt/app-root/src
RUN chmod 755 /generate-config.sh \
    && chown -R 10000:10001 /opt/app-root /var/log/nginx /etc/nginx/conf.d /var/lib/nginx \
    && touch /var/run/nginx.pid \
    && chown 10000:10001 /var/run/nginx.pid
USER 10000
EXPOSE 8080
ENTRYPOINT ["/generate-config.sh"]
