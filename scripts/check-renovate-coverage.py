#!/usr/bin/env python3
"""Vérifie que Renovate suit toutes les versions épinglées des Applications.

Le manager argocd natif de Renovate ne lit pas gitops/apps/templates/ (YAML
templaté par Helm) : renovate.json les suit par expressions régulières, qui
dépendent de la forme exacte des fichiers. Ce contrôle échoue si :
  - une source `chart:` d'un template n'est reconnue par aucune regex
    (ordre repoURL → chart → targetRevision non respecté, version templatée…) ;
  - un `tag:` d'image dans les valeurs Helm n'a pas de commentaire
    `# renovate: datasource=… depName=…` juste au-dessus.
Sans ce contrôle, une version non suivie serait ignorée en silence.
"""
import glob
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def js_to_py(pattern: str) -> re.Pattern:
    return re.compile(pattern.replace("(?<", "(?P<").replace("(?P<=", "(?<=").replace("(?P<!", "(?<!"))


def main() -> int:
    config = json.loads((ROOT / "renovate.json").read_text())
    regexes = []
    for manager in config.get("customManagers", []):
        file_patterns = [re.compile(p.strip("/")) for p in manager["managerFilePatterns"]]
        regexes.append((file_patterns, [js_to_py(s) for s in manager["matchStrings"]]))

    errors = []
    for path in sorted(glob.glob(str(ROOT / "gitops/apps/templates/*.yaml"))):
        rel = str(Path(path).relative_to(ROOT))
        text = Path(path).read_text()
        matched_offsets = set()
        for file_patterns, strings in regexes:
            if not any(p.search(rel) for p in file_patterns):
                continue
            for rx in strings:
                for m in rx.finditer(text):
                    matched_offsets.update(range(m.start(), m.end()))

        lines = text.splitlines(keepends=True)
        offset = 0
        for number, line in enumerate(lines, 1):
            stripped = line.strip()
            if re.match(r"chart:\s*\S", stripped) and offset + line.index("chart") not in matched_offsets:
                errors.append(f"{rel}:{number}: source `chart:` non suivie par Renovate")
            if re.match(r"tag:\s*\S", stripped):
                previous = lines[number - 2].strip() if number > 1 else ""
                if not previous.startswith("# renovate:"):
                    errors.append(f"{rel}:{number}: `tag:` sans commentaire `# renovate:` au-dessus")
            offset += len(line)

    for error in errors:
        print(error, file=sys.stderr)
    if errors:
        print("Voir renovate.json et docs/manuel-admin.md (Mises à jour des briques).", file=sys.stderr)
        return 1
    print("Toutes les versions des templates sont suivies par Renovate.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
