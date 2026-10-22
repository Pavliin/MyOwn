#!/usr/bin/env python3
"""Garde-fou sur les fichiers *.sops.yaml du dépôt.

SOPS chiffre les VALEURS, jamais les NOMS de clés. Le 2026-10-15, un jeton
Gandi s'est retrouvé comme nom de clé d'un secret chiffré, donc en clair
dans ce dépôt public pendant 7 jours (docs/notes-techniques.md, « Incident :
jeton Gandi publié en clair comme nom de clé SOPS »). Ce script refuse :

  - un fichier qui n'est pas chiffré (pas de bloc `sops` avec `mac`) ;
  - une valeur non chiffrée (tout doit être `ENC[...]`, .sops.yaml ne
    définit aucune exception) ;
  - un nom de clé qui ressemble à un secret plutôt qu'à un nom : longue
    suite hexadécimale, chaîne de type base64, caractères inattendus.

Il n'affiche jamais un nom suspect en entier, pour ne pas republier le
secret dans les logs de CI.

Usage :
  scripts/check-sops-files.py              # tous les *.sops.yaml suivis par git
  scripts/check-sops-files.py --staged     # ceux de l'index (hook pre-commit)
  scripts/check-sops-files.py FICHIER...   # fichiers donnés
"""
import re
import subprocess
import sys

import yaml

KEY_SHAPE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.\-]{0,63}$")
HEX_RUN = re.compile(r"[0-9a-fA-F]{16,}")
SEPARATORS = re.compile(r"[_.\-]")


def mask(name):
    return f"{name[:4]}… ({len(name)} caractères)"


def key_problem(name):
    if not isinstance(name, str):
        return "nom de clé non textuel"
    if not KEY_SHAPE.match(name):
        return "caractères ou longueur inattendus"
    if HEX_RUN.search(name):
        return "longue suite hexadécimale (ressemble à un jeton)"
    if len(name) >= 20 and not SEPARATORS.search(name) and re.search(r"\d", name) and re.search(r"[a-z]", name) and re.search(r"[A-Z]", name):
        return "chaîne aléatoire sans séparateur (ressemble à un jeton)"
    return None


def walk(node, path, problems):
    if isinstance(node, dict):
        for k, v in node.items():
            why = key_problem(k)
            if why:
                problems.append(f"{'.'.join(path) or '(racine)'} : clé {mask(str(k))} — {why}")
                shown = mask(str(k))
            else:
                shown = k
            walk(v, path + [shown], problems)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            walk(v, path + [f"[{i}]"], problems)
    elif not (isinstance(node, str) and node.startswith("ENC[AES256_GCM,")):
        problems.append(f"{'.'.join(map(str, path))} : valeur NON chiffrée")


def check(label, text):
    try:
        doc = yaml.safe_load(text)
    except yaml.YAMLError as e:
        return [f"YAML illisible ({e.__class__.__name__})"]
    if not isinstance(doc, dict):
        return ["contenu inattendu (pas un objet YAML)"]
    meta = doc.get("sops")
    if not isinstance(meta, dict) or not meta.get("mac"):
        return ["pas chiffré par sops (bloc `sops` ou `mac` absent)"]
    problems = []
    walk({k: v for k, v in doc.items() if k != "sops"}, [], problems)
    return problems


def git_lines(*args):
    return [l for l in subprocess.check_output(["git", *args], text=True).splitlines() if l]


def main(argv):
    is_sops = re.compile(r"(^|/)[^/]+\.sops\.ya?ml$")  # pas .sops.yaml lui-même (config sops)
    if argv[:1] == ["--staged"]:
        paths = [p for p in git_lines("diff", "--cached", "--name-only", "--diff-filter=ACMR") if is_sops.search(p)]
        files = [(p, subprocess.check_output(["git", "show", f":{p}"], text=True)) for p in paths]
    elif argv:
        files = [(p, open(p, encoding="utf-8").read()) for p in argv]
    else:
        files = [(p, open(p, encoding="utf-8").read()) for p in git_lines("ls-files") if is_sops.search(p)]

    failed = 0
    for path, text in files:
        problems = check(path, text)
        if problems:
            failed += 1
            print(f"✗ {path}")
            for p in problems:
                print(f"    {p}")
    print(f"{len(files)} fichier(s) sops vérifié(s), {failed} en erreur.")
    if failed:
        print("Rappel : sops ne chiffre jamais les noms de clés — relire `sops -d --output-type json <f> | jq '.stringData | keys'`.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
