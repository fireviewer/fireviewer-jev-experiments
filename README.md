# FireViewer — expérimentations Jev / TypeSafe

Laboratoire public de comparaison **d'une brique textuelle à la fois** dans FireViewer.
Jev qualifie des textes et consolide, réfute ou nuance des propositions. Les pixels
restent traités par les modèles de vision ; distances, dates, hashes, géométrie,
tolérances et fusion temporelle restent dans le code déterministe.

**État du 21 septembre 2026 : campagne suspendue à la demande de l'utilisateur.**
Deux contrôles Jev ont été exécutés sur 48 sources. Deux sondes du juge Bonsaï ont
fonctionné sur GPU. Aucune comparaison de journées complètes n'est terminée,
et aucun gagnant qualitatif n'est établi. Les machines du laboratoire ont été arrêtées.

## Démarrage local

Python 3.11+ ; Node 24 pour le tableau. Le noyau Jev utilise la bibliothèque standard.

```sh
cd jev-integration/dashboard
npm ci
npm run build
cd ../..
python3 jev-integration/server.py --port 8765
```

Ouvrir http://127.0.0.1:8765. Choisir une brique, importer les cas JSON/JSONL,
préparer l'essai, puis activer explicitement les appels réels. Le formulaire
« Configurer TypeSafe » garde la clé en mémoire du serveur. Ne pas la mettre dans
un fichier suivi, une URL, une capture ou une conversation. Le mode hors ligne
prépare les contrats sans inventer de résultat de modèle.

```sh
python3 -m unittest discover -s jev-integration/tests -v
python3 jev-integration/component_runner.py examples/fv01.synthetic.jsonl \
  --component FV-01 --output /tmp/jev-plan.json
```

L'interface affiche la progression, les décisions typées, coûts et latences mesurés,
les erreurs, l'historique, les exports JSON et les captures PNG. Ces données privées
sont écrites dans `.local/typesafe-lab/`. Le tableau n'exécute pas à lui seul toute
la reconstruction d'un incendie.

## Navigation

- [Architecture et limites](docs/ARCHITECTURE.md)
- [Les douze contrats](docs/COMPONENTS.md)
- [Protocole quotidien et comparaison](docs/PROTOCOL.md)
- [Résultats réellement obtenus](docs/RESULTS.md)
- [Données, collecte et droits](docs/DATA.md)
- [Exécution, suivi et reprise](docs/OPERATIONS.md)
- [Secrets et publication](docs/SECURITY.md)
- [Validation du code publié](docs/VALIDATION.md)

Les changements Bonsaï du pipeline standard sont dans `fireviewer-contracts`,
`fireviewer-vision-runtime` et `fireviewer-orchestrator`. Le déploiement AWS et
la recette GPU appartiennent au dépôt privé `fireviewer-docker`. Voir
`manifests/pipeline-commits.json` pour les révisions associées. Aucun code backend
privé, média tiers, poids de modèle ni rapport utilisateur intégral n'est publié ici.

Captures du parcours synthétique vérifié : [bureau](results/publication/jev-components-desktop.png) · [mobile](results/publication/jev-components-mobile.png). Aucun résultat de modèle n’est simulé dans ces captures.
