"""Fonctions communes : acces MySQL Finnovatix (docker exec), lecture de l'API Kafundo, et reproduction EXACTE de
la detection de changement de la synchro (FundingChangeDetectionService::diff + SyncKafundoFundingCallsCommand::mapDevice).

Aucune ecriture ici. Variables : MYSQL_EXEC (commande complete, defaut : conteneur MySQL de production, mot de passe lu
dans le conteneur), API_URL (defaut http://127.0.0.1:8000), AUDIT_DIR."""
import json, os, shlex, subprocess, urllib.request

AUDIT_DIR = os.environ.get("AUDIT_DIR", "/opt/finveille-backups/audit_20261010")
API_URL = os.environ.get("API_URL", "http://127.0.0.1:8000")
MYSQL_CONTAINER = os.environ.get("MYSQL_CONTAINER", "finnovatix-platform-finnovatix-mysql-1")
MATERIAL_FIELDS = ("deadline", "funding_max", "status")


def my(sql):
    """Execute du SQL, retourne la sortie brute (tab-separated, sans en-tete)."""
    custom = os.environ.get("MYSQL_EXEC")
    if custom:
        cmd = shlex.split(custom)
    else:
        cmd = ["docker", "exec", "-i", MYSQL_CONTAINER, "sh", "-c",
               'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql -uroot --default-character-set=utf8mb4 --batch --skip-column-names finnovatix']
    r = subprocess.run(cmd, input=sql.encode(), capture_output=True)
    out = r.stdout.decode("utf-8", errors="replace")
    err = "\n".join(l for l in r.stderr.decode("utf-8", errors="replace").splitlines() if "Using a password" not in l)
    if r.returncode != 0 or ("ERROR" in err and "ERROR" not in out):
        raise SystemExit("erreur MySQL: " + err[:300])
    return out


def _get(u):
    with urllib.request.urlopen(u, timeout=60) as r:
        return json.load(r)


def api_devices(max_passes=40):
    """Instantane COMPLET des dispositifs publics de l'API Kafundo.

    La pagination de l'API n'est pas deterministe (tri avec egalites : ~20 % des fiches manquent a chaque parcours,
    d'autres sont dupliquees). Un seul parcours donnerait donc un instantane incomplet, different a chaque lecture ;
    on cumule des parcours jusqu'a atteindre `total` fiches distinctes (ou stabilite)."""
    seen, stable, total = {}, 0, 0
    for _ in range(max_passes):
        page, before = 1, len(seen)
        while True:
            d = _get(f"{API_URL}/api/v1/devices/?page={page}&page_size=100")
            batch = d.get("items") or []
            if not batch:
                break
            for i in batch:
                if i.get("id"):
                    seen[i["id"]] = i
            total = int(d.get("total") or total)
            page += 1
            if page > (total // 100) + 2:
                break
        if total and len(seen) >= total:
            break
        stable = stable + 1 if len(seen) == before else 0
        if stable >= 3:
            break
    return seen


def api_detail(device_id):
    try:
        return _get(f"{API_URL}/api/v1/devices/{device_id}")
    except Exception:
        return None


def blank_to_null(v):
    if not isinstance(v, str):
        return None
    v = v.strip()
    return v or None


def numeric_or_null(v):
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def date_or_null(v):
    if not isinstance(v, str) or not v.strip():
        return None
    return v.strip()[:10]


def mapped(device):
    """Valeurs que la synchro ecrirait pour les 3 champs materiels (mapDevice)."""
    return {
        "deadline": date_or_null(device.get("close_date")),
        "funding_max": numeric_or_null(device.get("amount_max")),
        "status": blank_to_null(device.get("status")) or "unknown",
    }


def _php_str(v):
    if v is None:
        return ""
    if isinstance(v, float):
        return "%.14g" % v
    return str(v)


def diff(current, device):
    """current : dict(deadline 'YYYY-MM-DD'|None, funding_max float|None, status str). Retourne la liste des changements
    que la prochaine synchro detecterait (donc notifierait)."""
    new = mapped(device)
    out = []
    for f in MATERIAL_FIELDS:
        n = new[f]
        if n is None:                       # `$new === null` => ignore
            continue
        o = current.get(f)
        if _php_str(o) != _php_str(n):
            out.append({"field": f, "old": o, "new": n})
    return out
