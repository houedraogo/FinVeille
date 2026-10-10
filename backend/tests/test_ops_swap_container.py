"""swap_container : reconstruction fidèle d'un `docker run` à partir de `docker inspect`."""
import sys
from pathlib import Path

OPS = Path(__file__).resolve().parents[2] / "scripts" / "ops"
sys.path.insert(0, str(OPS))

import swap_container as sc  # noqa: E402


def backend_inspect():
    return {
        "Id": "100132a80bdff1393d87e783ea9ce3049fced264f67f3d664378b999b9436c88",
        "Name": "/kafundo-backend",
        "Config": {
            "Image": "kafundo-backend:a105718",
            "Cmd": ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"],
            "Entrypoint": None, "WorkingDir": "/app", "User": "",
            "Labels": {"maintainer": "kafundo"},
            "Env": ["PATH=/usr/bin", "PYTHON_VERSION=3.11", "DEBUG=false", "STRIPE_PRICE_PRO=price_1", "TOKEN_X=abc"],
        },
        "HostConfig": {
            "NetworkMode": "kafundo_default",
            "PortBindings": {"8000/tcp": [{"HostIp": "", "HostPort": "8000"}]},
            "RestartPolicy": {"Name": "unless-stopped", "MaximumRetryCount": 0},
            "Binds": None, "Memory": 0,
        },
        "NetworkSettings": {"Networks": {"kafundo_default": {"Aliases": ["backend", "100132a80bdf"]}}},
    }


def test_run_args_replay_network_alias_ports_restart_cmd_and_workdir():
    args = sc.build_run_args(backend_inspect(), "kafundo-backend", "kafundo-backend:new", "/tmp/env")
    joined = " ".join(args)
    assert args[:4] == ["run", "-d", "--name", "kafundo-backend"]
    assert "--network kafundo_default" in joined
    assert "--network-alias backend" in joined and "100132a80bdf" not in joined      # alias auto-généré ignoré
    assert "-p 8000:8000" in joined and "--restart unless-stopped" in joined
    assert "-w /app" in joined and "--label maintainer=kafundo" in joined
    assert "--env-file /tmp/env kafundo-backend:new uvicorn app.main:app --host 0.0.0.0 --port 8000" in joined
    assert "-u" not in args                                                           # pas d'utilisateur : inchangé


def test_entrypoint_and_binds_and_memory_are_preserved():
    inspected = backend_inspect()
    inspected["Config"]["Entrypoint"] = ["docker-entrypoint.sh"]
    inspected["Config"]["Cmd"] = ["npm", "run", "start"]
    inspected["HostConfig"]["Binds"] = ["/data:/data:ro"]
    inspected["HostConfig"]["Memory"] = 536870912
    joined = " ".join(sc.build_run_args(inspected, "n", "img", "/tmp/e"))
    assert "--entrypoint docker-entrypoint.sh" in joined and "-v /data:/data:ro" in joined and "--memory 536870912" in joined
    assert joined.endswith("img npm run start")


def test_compose_labels_are_not_replayed():
    inspected = backend_inspect()
    inspected["Config"]["Labels"] = {"com.docker.compose.project": "x", "maintainer": "kafundo"}
    joined = " ".join(sc.build_run_args(inspected, "n", "img", "/tmp/e"))
    assert "com.docker.compose" not in joined


def test_explicit_env_excludes_values_baked_in_the_image():
    image = {"Config": {"Env": ["PATH=/usr/bin", "PYTHON_VERSION=3.11"]}}
    env = sc.explicit_env(backend_inspect(), image)
    assert set(env) == {"DEBUG", "STRIPE_PRICE_PRO", "TOKEN_X"}


def test_merge_env_only_overrides_existing_keys_unless_listed():
    base = {"A": "1", "B": "2"}
    overrides = {"A": "new", "C": "3"}
    assert sc.merge_env(base, overrides) == {"A": "new", "B": "2"}                  # C absent du conteneur : ignoré
    assert sc.merge_env(base, overrides, only={"C"}) == {"A": "1", "B": "2", "C": "3"}


def test_env_file_is_written_0600_without_newlines(tmp_path):
    path = sc._write_env_file(str(tmp_path), {"K": "v", "SECRET": "x=y"})
    assert Path(path).read_text(encoding="utf-8") == "K=v\nSECRET=x=y\n"
    try:
        sc._write_env_file(str(tmp_path), {"BAD": "a\nb"})
    except ValueError:
        pass
    else:
        raise AssertionError("une valeur multiligne doit être refusée")
