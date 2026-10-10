"""Recrée un conteneur à l'identique (nouvelle image et/ou nouvel environnement) avec retour arrière.

Pourquoi : les conteneurs applicatifs de Kafundo (backend, worker, beat, frontend) ont été lancés
avec `docker run` (aucun label docker compose). `docker compose up --force-recreate` ne sait donc
pas les remplacer. Cet outil relit la configuration réelle du conteneur (`docker inspect`) et la
rejoue à l'identique : réseau, alias, ports, politique de redémarrage, commande, volumes,
variables d'environnement explicites.

Sécurité des secrets : l'environnement n'est jamais affiché ; il transite par un fichier 0600 dans
un dossier 0700 détruit à la sortie. Les surcharges d'environnement viennent d'un fichier .env.

Commandes
    plan   NOM [--image IMG]                       affiche la configuration rejouée (sans valeurs d'environnement)
    swap   NOM --image IMG [--env-from FICHIER] [--env-only CLE,CLE] [--health CMD] [--wait SEC] [--stop-timeout SEC]
    run-once --image IMG [--mount H:C ...] NOM -- CMD...   conteneur jetable : même réseau et même environnement que NOM
    rollback NOM                                   remet l'ancien conteneur (NOM-prev) en service
    commit NOM                                     supprime l'ancien conteneur (NOM-prev) une fois la validation faite

`swap` : renomme l'ancien en NOM-prev (arrêté, redémarrage désactivé), démarre le nouveau, attend la
santé ; en cas d'échec il se retire et rétablit l'ancien automatiquement.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Optional

PREV_SUFFIX = "-prev"


def _docker(*args: str, check: bool = True, capture: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["docker", *args], check=check, capture_output=capture, text=True)


def inspect(name: str) -> dict[str, Any]:
    return json.loads(_docker("inspect", name).stdout)[0]


def parse_env_file(path: str | Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value
    return values


def explicit_env(container: dict[str, Any], image: dict[str, Any]) -> dict[str, str]:
    """Variables posées au lancement du conteneur (celles de l'image sont exclues)."""
    current = dict(e.split("=", 1) for e in (container["Config"].get("Env") or []))
    baked = dict(e.split("=", 1) for e in (image["Config"].get("Env") or []))
    return {k: v for k, v in current.items() if baked.get(k) != v}


def merge_env(base: dict[str, str], overrides: dict[str, str], only: Optional[set[str]] = None) -> dict[str, str]:
    """Applique les surcharges du fichier .env (uniquement les clés déjà présentes, ou listées dans `only`)."""
    merged = dict(base)
    for key, value in overrides.items():
        if only is not None:
            if key in only:
                merged[key] = value
        elif key in merged:
            merged[key] = value
    return merged


def build_run_args(container: dict[str, Any], name: str, image: str, env_file: str) -> list[str]:
    """Arguments `docker run` rejouant la configuration d'un conteneur existant."""
    config, host = container["Config"], container["HostConfig"]
    args = ["run", "-d", "--name", name]

    network = host.get("NetworkMode") or "default"
    args += ["--network", network]
    networks = container.get("NetworkSettings", {}).get("Networks", {})
    short_id = container.get("Id", "")[:12]
    for alias in (networks.get(network, {}) or {}).get("Aliases") or []:
        if alias and alias != short_id and alias != container["Name"].lstrip("/"):
            args += ["--network-alias", alias]

    for port, bindings in (host.get("PortBindings") or {}).items():
        for binding in bindings or []:
            host_ip = binding.get("HostIp") or ""
            host_port = binding.get("HostPort") or ""
            container_port = port.split("/")[0]
            proto = port.split("/")[1] if "/" in port else "tcp"
            mapping = f"{host_ip + ':' if host_ip else ''}{host_port}:{container_port}"
            args += ["-p", mapping + ("" if proto == "tcp" else f"/{proto}")]

    restart = (host.get("RestartPolicy") or {}).get("Name")
    if restart:
        args += ["--restart", restart if restart != "on-failure" else f"on-failure:{host['RestartPolicy'].get('MaximumRetryCount', 0)}"]
    for bind in host.get("Binds") or []:
        args += ["-v", bind]
    if host.get("Memory"):
        args += ["--memory", str(host["Memory"])]
    if config.get("WorkingDir"):
        args += ["-w", config["WorkingDir"]]
    if config.get("User"):
        args += ["-u", config["User"]]
    for key, value in (config.get("Labels") or {}).items():
        if not key.startswith("com.docker.compose") and not key.startswith("org.opencontainers"):
            args += ["--label", f"{key}={value}"]
    if config.get("Entrypoint"):
        args += ["--entrypoint", config["Entrypoint"][0]]
    args += ["--env-file", env_file, image]
    if config.get("Entrypoint") and len(config["Entrypoint"]) > 1:
        args += config["Entrypoint"][1:]
    args += list(config.get("Cmd") or [])
    return args


def _write_env_file(directory: str, env: dict[str, str]) -> str:
    path = os.path.join(directory, "container.env")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        for key, value in env.items():
            if "\n" in value or "\r" in value:
                raise ValueError(f"La variable {key} contient un saut de ligne : non transmissible par env-file")
            handle.write(f"{key}={value}\n")
    return path


def _healthy(name: str, health_cmd: Optional[str]) -> bool:
    state = inspect(name)["State"]
    if not state.get("Running") or state.get("Restarting"):
        return False
    if health_cmd is None:
        return True
    return _docker("exec", name, "sh", "-c", health_cmd, check=False).returncode == 0


def swap(name: str, image: str, env_from: Optional[str], env_only: Optional[set[str]], health_cmd: Optional[str],
         wait: int, stop_timeout: int) -> int:
    old = inspect(name)
    base_image = inspect(old["Config"]["Image"]) if _docker("image", "inspect", old["Config"]["Image"], check=False).returncode == 0 else {"Config": {"Env": []}}
    env = explicit_env(old, base_image)
    if env_from:
        env = merge_env(env, parse_env_file(env_from), env_only)
    prev = name + PREV_SUFFIX
    if _docker("container", "inspect", prev, check=False).returncode == 0:
        print(f"ARRÊT: {prev} existe déjà (swap précédent non validé). Utilisez commit ou rollback d'abord.", file=sys.stderr)
        return 2

    workdir = tempfile.mkdtemp()
    os.chmod(workdir, 0o700)
    try:
        env_file = _write_env_file(workdir, env)
        run_args = build_run_args(old, name, image, env_file)
        restart_policy = (old["HostConfig"].get("RestartPolicy") or {}).get("Name") or "no"

        print(f"1/4 arrêt de {name} (délai {stop_timeout}s) et mise de côté sous {prev}")
        _docker("rename", name, prev)
        _docker("update", "--restart=no", prev)
        _docker("stop", "-t", str(stop_timeout), prev)

        print(f"2/4 démarrage du nouveau {name} sur l'image {image}")
        started = _docker(*run_args, check=False)
        if started.returncode != 0:
            print("Échec du démarrage:", started.stderr.strip().splitlines()[-1:] or started.stderr, file=sys.stderr)
            _rollback_after_failure(name, prev, restart_policy)
            return 1

        print(f"3/4 attente de la santé (max {wait}s)")
        deadline = time.time() + wait
        while time.time() < deadline:
            if _healthy(name, health_cmd):
                break
            time.sleep(2)
        else:
            print(f"Le nouveau {name} n'est pas sain après {wait}s — retour arrière", file=sys.stderr)
            _rollback_after_failure(name, prev, restart_policy)
            return 1
        print(f"4/4 OK — {name} tourne sur {image}. Ancien conteneur conservé: {prev} (rollback possible).")
        return 0
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def _rollback_after_failure(name: str, prev: str, restart_policy: str) -> None:
    _docker("rm", "-f", name, check=False)
    _docker("rename", prev, name)
    _docker("update", f"--restart={restart_policy}", name, check=False)
    _docker("start", name)
    print(f"Retour arrière effectué : l'ancien {name} a été remis en service.", file=sys.stderr)


def rollback(name: str) -> int:
    prev = name + PREV_SUFFIX
    if _docker("container", "inspect", prev, check=False).returncode != 0:
        print(f"Aucun {prev} à restaurer.", file=sys.stderr)
        return 2
    restart_policy = (inspect(prev)["HostConfig"].get("RestartPolicy") or {}).get("Name") or "no"
    policy = restart_policy if restart_policy != "no" else "unless-stopped"
    _docker("rm", "-f", name, check=False)
    _docker("rename", prev, name)
    _docker("update", f"--restart={policy}", name, check=False)
    _docker("start", name)
    print(f"{name} restauré depuis {prev}.")
    return 0


def commit(name: str) -> int:
    prev = name + PREV_SUFFIX
    if _docker("container", "inspect", prev, check=False).returncode != 0:
        print(f"Aucun {prev} à supprimer.", file=sys.stderr)
        return 2
    _docker("rm", prev)
    print(f"{prev} supprimé : bascule validée.")
    return 0


def run_once(name: str, image: str, mounts: list[str], command: list[str]) -> int:
    """Exécute une commande ponctuelle dans l'environnement exact de `name` (migration, rapport…)."""
    source = inspect(name)
    base_image = inspect(source["Config"]["Image"])
    env = explicit_env(source, base_image)
    workdir = tempfile.mkdtemp()
    os.chmod(workdir, 0o700)
    try:
        env_file = _write_env_file(workdir, env)
        args = ["run", "--rm", "--network", source["HostConfig"].get("NetworkMode") or "default", "--env-file", env_file]
        if source["Config"].get("WorkingDir"):
            args += ["-w", source["Config"]["WorkingDir"]]
        for mount in mounts:
            args += ["-v", mount]
        args += [image, *command]
        return subprocess.run(["docker", *args]).returncode
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def plan(name: str, image: Optional[str]) -> int:
    old = inspect(name)
    args = build_run_args(old, name, image or old["Config"]["Image"], "<fichier-env-0600>")
    print("docker " + " ".join(args))
    base_image = inspect(old["Config"]["Image"])
    print(f"({len(explicit_env(old, base_image))} variables d'environnement explicites rejouées, valeurs non affichées)")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("plan"); p.add_argument("name"); p.add_argument("--image")
    s = sub.add_parser("swap"); s.add_argument("name"); s.add_argument("--image", required=True)
    s.add_argument("--env-from"); s.add_argument("--env-only", help="clés (séparées par des virgules) à écraser/ajouter depuis --env-from")
    s.add_argument("--health", help="commande exécutée DANS le conteneur ; code 0 = sain"); s.add_argument("--wait", type=int, default=90)
    s.add_argument("--stop-timeout", type=int, default=30)
    o = sub.add_parser("run-once"); o.add_argument("name"); o.add_argument("--image", required=True)
    o.add_argument("--mount", action="append", default=[]); o.add_argument("cmd", nargs=argparse.REMAINDER)
    r = sub.add_parser("rollback"); r.add_argument("name")
    c = sub.add_parser("commit"); c.add_argument("name")
    args = parser.parse_args(argv)
    if args.command == "plan":
        return plan(args.name, args.image)
    if args.command == "swap":
        only = set(args.env_only.split(",")) if args.env_only else None
        return swap(args.name, args.image, args.env_from, only, args.health, args.wait, args.stop_timeout)
    if args.command == "run-once":
        command = args.cmd[1:] if args.cmd and args.cmd[0] == "--" else args.cmd
        if not command:
            parser.error("run-once: commande manquante après --")
        return run_once(args.name, args.image, args.mount, command)
    if args.command == "rollback":
        return rollback(args.name)
    return commit(args.name)


if __name__ == "__main__":
    sys.exit(main())
