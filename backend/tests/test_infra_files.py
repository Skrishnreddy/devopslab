"""Infrastructure validation: configs the scripts depend on stay safe."""
import os

import yaml

from app.core.config import REPO_ROOT

INFRA = REPO_ROOT / "infra"


def test_kind_ports_bind_to_loopback_only():
    cfg = yaml.safe_load((INFRA / "kind" / "cluster.yaml").read_text())
    mappings = [m for n in cfg["nodes"] for m in n.get("extraPortMappings", [])]
    assert mappings and all(m["listenAddress"] == "127.0.0.1" for m in mappings)
    assert [n["role"] for n in cfg["nodes"]].count("worker") == 2


def test_scripts_are_executable_and_strict():
    for script in (INFRA / "scripts").glob("*.sh"):
        assert os.access(script, os.X_OK), script
        text = script.read_text()
        assert "set -euo pipefail" in text or "lib.sh" in text, script


def test_config_env_matches_backend_defaults():
    from app.core.config import Settings
    env = dict(line.split("=", 1) for line in (INFRA / "config.env").read_text().splitlines()
               if line and not line.startswith("#"))
    s = Settings()
    assert env["COLIMA_PROFILE"] == s.colima_profile and env["CLUSTER_NAME"] == s.cluster_name


def test_images_script_builds_every_local_image_the_code_uses():
    """Images with imagePullPolicy Never must be built by images.sh with the same tag."""
    import re

    from app.providers.terminal import IMAGE
    built = set(re.findall(r'"(devopslab/[a-z0-9-]+:[0-9.]+)=', (INFRA / "scripts" / "images.sh").read_text()))
    used = {IMAGE} | {doc_image for f in (REPO_ROOT / "labs").glob("*/*.yaml")
                      for doc_image in re.findall(r"image: (devopslab/\S+)", f.read_text())}
    assert used and used == built
