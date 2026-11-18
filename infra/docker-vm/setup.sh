#!/bin/sh
# Runs as root inside the Docker VM (devopslab-docker) on every `docker-vm.sh up`.
#
# 1. AppArmor profile `devopslab-sandbox`. Ubuntu 24.04 blocks unprivileged
#    user namespaces (kernel.apparmor_restrict_unprivileged_userns=1), which
#    rootless Docker needs. Instead of turning that off for the whole VM, this
#    profile allows user namespaces only for processes started under it, i.e.
#    the sandbox containers (docker run --security-opt apparmor=devopslab-sandbox).
#
# 2. Firewall. Containers may reach the internet (image pulls) and DNS, but nothing on the
# VM's own gateway network. On Colima/Lima that gateway forwards to your Mac's
# localhost, so this is what keeps sandboxes away from the DevOpsLab API,
# Ollama and the cluster API server. Containers also can't open connections to
# the VM itself.
set -eu
cat > /etc/apparmor.d/devopslab-sandbox <<'PROFILE'
abi <abi/4.0>,
include <tunables/global>

profile devopslab-sandbox flags=(unconfined) {
  userns,
}
PROFILE
apparmor_parser -r -W /etc/apparmor.d/devopslab-sandbox
echo "apparmor: devopslab-sandbox profile loaded (user namespaces for sandboxes only)"

GW="$(ip route | awk '/^default/ {print $3; exit}')"
[ -n "$GW" ] || { echo "no default route" >&2; exit 1; }
NET="${GW%.*}.0/24"
DNS="$(awk '/^nameserver/ {print $2; exit}' /etc/resolv.conf)"

# Forwarded container traffic (DOCKER-USER is evaluated before Docker's own rules).
iptables -N DEVOPSLAB-SANDBOX 2>/dev/null || iptables -F DEVOPSLAB-SANDBOX
iptables -A DEVOPSLAB-SANDBOX -m conntrack --ctstate ESTABLISHED,RELATED -j RETURN
case "$DNS" in
  "${GW%.*}".*)
    iptables -A DEVOPSLAB-SANDBOX -d "$DNS" -p udp --dport 53 -j RETURN
    iptables -A DEVOPSLAB-SANDBOX -d "$DNS" -p tcp --dport 53 -j RETURN ;;
esac
iptables -A DEVOPSLAB-SANDBOX -d "$NET" -j REJECT
iptables -A DEVOPSLAB-SANDBOX -d 169.254.0.0/16 -j REJECT
iptables -N DOCKER-USER 2>/dev/null || true
iptables -C DOCKER-USER -j DEVOPSLAB-SANDBOX 2>/dev/null || iptables -I DOCKER-USER -j DEVOPSLAB-SANDBOX

# Container -> VM itself (INPUT): only replies to connections the VM opened.
iptables -N DEVOPSLAB-SANDBOX-IN 2>/dev/null || iptables -F DEVOPSLAB-SANDBOX-IN
iptables -A DEVOPSLAB-SANDBOX-IN -m conntrack --ctstate ESTABLISHED,RELATED -j RETURN
iptables -A DEVOPSLAB-SANDBOX-IN -p udp --dport 53 -j RETURN
iptables -A DEVOPSLAB-SANDBOX-IN -p tcp --dport 53 -j RETURN
iptables -A DEVOPSLAB-SANDBOX-IN -j REJECT
for IF in docker0 br-+; do
  iptables -C INPUT -i "$IF" -j DEVOPSLAB-SANDBOX-IN 2>/dev/null || iptables -I INPUT -i "$IF" -j DEVOPSLAB-SANDBOX-IN
done
echo "firewall: blocked $NET (gateway $GW) and link-local for containers; DNS $DNS"
