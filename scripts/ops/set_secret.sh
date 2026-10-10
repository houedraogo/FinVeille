#!/usr/bin/env bash
# Remplace un secret dans un ou plusieurs fichiers d'environnement, sans jamais l'afficher.
#
#   sudo bash scripts/ops/set_secret.sh STRIPE_SECRET_KEY .env .env.production
#
# La valeur est saisie en mode masqué (deux fois) DANS VOTRE TERMINAL : elle ne passe ni par
# un argument, ni par l'historique du shell, ni par une conversation avec un assistant.
# Une sauvegarde 0600 de chaque fichier est créée ; supprimez-la après vérification :
#   shred -u .env.rotation-bak.*
set -euo pipefail

if [ "$#" -lt 2 ]; then
  echo "Usage: $0 NOM_VARIABLE fichier_env [fichier_env ...]" >&2
  exit 2
fi
KEY="$1"; shift
HERE="$(cd "$(dirname "$0")" && pwd)"

for f in "$@"; do
  [ -f "$f" ] || { echo "Fichier introuvable: $f" >&2; exit 1; }
done

read -rsp "Nouvelle valeur pour ${KEY} (saisie masquée) : " VALUE1; echo
read -rsp "Confirmez la valeur : " VALUE2; echo
if [ "$VALUE1" != "$VALUE2" ] || [ -z "$VALUE1" ]; then
  echo "Les deux saisies diffèrent ou sont vides : aucune modification." >&2
  unset VALUE1 VALUE2
  exit 1
fi

umask 077
STAMP="$(date +%Y%m%d%H%M%S)"
for f in "$@"; do
  cp -p "$f" "$(dirname "$f")/.env.rotation-bak.$(basename "$f").$STAMP"
  chmod 600 "$(dirname "$f")/.env.rotation-bak.$(basename "$f").$STAMP"
  printf '%s' "$VALUE1" | python3 "$HERE/envfile.py" set "$f" "$KEY"
done
unset VALUE1 VALUE2
echo "Terminé. Redémarrez les services concernés puis vérifiez (voir docs/SECRETS_ROTATION_RUNBOOK.md)."
echo "Sauvegardes à supprimer après vérification : .env.rotation-bak.*"
