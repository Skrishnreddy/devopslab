# DevOpsLab Docker terminal sandbox (Phase 2b, docs/security/terminal.md).
# Runs ONLY in the separate Docker VM (profile devopslab-docker), never in the
# lab cluster. Docker's rootless dind image: dockerd runs as uid 1000 inside a
# user namespace, and so does the learner's shell. The container needs
# --privileged for the nested user namespace; the VM is the isolation boundary.
# Build context: images/ (see infra/scripts/docker-vm.sh).
FROM docker:27.5.1-dind-rootless

USER root
RUN apk add --no-cache bash bash-completion curl git jq nano vim less procps htop \
        iproute2 bind-tools ca-certificates tini ncurses
COPY terminal/bashrc /etc/devopslab/bashrc
COPY docker-terminal/entrypoint.sh /usr/local/bin/devopslab-entrypoint
RUN chmod 0755 /usr/local/bin/devopslab-entrypoint \
    && cp /etc/devopslab/bashrc /home/rootless/.bashrc \
    && printf '[ -f ~/.bashrc ] && . ~/.bashrc\n' > /home/rootless/.bash_profile \
    && chown rootless:rootless /home/rootless/.bashrc /home/rootless/.bash_profile

USER rootless
ENV DEVOPSLAB_PROFILE=docker XDG_RUNTIME_DIR=/run/user/1000 DOCKER_HOST=unix:///run/user/1000/docker.sock
ENTRYPOINT ["/sbin/tini", "--", "devopslab-entrypoint"]
