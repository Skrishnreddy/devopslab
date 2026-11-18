# DevOpsLab terminal sandbox image (Linux + Kubernetes profiles).
# Runs as the non-root user "learner" (uid 1000). Built for the host arch
# (arm64 on Apple Silicon) by `make images` and loaded into kind.
FROM ubuntu:24.04

ARG TARGETARCH
ARG KUBECTL_VERSION=v1.31.4
ARG HELM_VERSION=v3.16.4

# hadolint ignore=DL3008
RUN apt-get update \
 && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      bash bash-completion ca-certificates curl less vim-tiny nano procps htop psmisc \
      iproute2 iputils-ping dnsutils netcat-openbsd jq git tree file man-db \
 && rm -rf /var/lib/apt/lists/*

# kubectl and helm, verified against upstream checksums.
RUN set -eux; arch="${TARGETARCH:-$(dpkg --print-architecture)}"; \
    curl -fsSLo /usr/local/bin/kubectl "https://dl.k8s.io/release/${KUBECTL_VERSION}/bin/linux/${arch}/kubectl"; \
    echo "$(curl -fsSL "https://dl.k8s.io/release/${KUBECTL_VERSION}/bin/linux/${arch}/kubectl.sha256")  /usr/local/bin/kubectl" | sha256sum -c -; \
    chmod 0755 /usr/local/bin/kubectl; \
    curl -fsSLo /tmp/helm.tgz "https://get.helm.sh/helm-${HELM_VERSION}-linux-${arch}.tar.gz"; \
    echo "$(curl -fsSL "https://get.helm.sh/helm-${HELM_VERSION}-linux-${arch}.tar.gz.sha256sum" | cut -d' ' -f1)  /tmp/helm.tgz" | sha256sum -c -; \
    tar -xzf /tmp/helm.tgz -C /tmp; install -m 0755 "/tmp/linux-${arch}/helm" /usr/local/bin/helm; rm -rf /tmp/helm.tgz "/tmp/linux-${arch}"; \
    kubectl completion bash > /etc/bash_completion.d/kubectl; helm completion bash > /etc/bash_completion.d/helm

# Rename the stock uid-1000 user to "learner". Home is an emptyDir at runtime
# (root filesystem is read-only), so the skeleton is copied in by the entrypoint.
RUN usermod -l learner -d /home/learner -m ubuntu && groupmod -n learner ubuntu
COPY bashrc /etc/devopslab/bashrc
COPY entrypoint.sh /usr/local/bin/devopslab-entrypoint
RUN chmod 0755 /usr/local/bin/devopslab-entrypoint

USER 1000:1000
WORKDIR /home/learner
ENV HOME=/home/learner TERM=xterm-256color LANG=C.UTF-8
ENTRYPOINT ["/usr/local/bin/devopslab-entrypoint"]
