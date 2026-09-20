# Exécution, suivi et reprise

## État de pause

Le laboratoire AWS est arrêté, disque conservé. L'endpoint Runpod conserve sa configuration
avec zéro worker ; le dernier job est annulé. Aucun service de collecte/comparaison local
ne doit relancer de calcul en arrière-plan. Le stockage conservé (EBS, objets, images)
reste facturable. Les autres projets du compte sont hors du périmètre de cet arrêt.

## Reprendre

1. Relire les reçus privés d'arrêt, vérifier le budget restant et les ressources existantes.
   Redémarrer la VM existante ; ne pas recréer de stack. Définir une nouvelle échéance
   d'arrêt sur AWS et pour Runpod avant toute remise à un worker.
2. Restaurer les sources/états sauvegardés et les reçus ; vérifier le manifeste figé.
   Identifier un périmètre/état initial admissible avant de qualifier la fusion quotidienne.
3. Assembler les trois composants aux commits de `manifests/pipeline-commits.json` avec
   la recette Bonsaï du dépôt `fireviewer-docker`. Le Dockerfile publié après la pause
   doit encore être construit/qualifié comme nouvel artefact ; les tests de sources
   utilisent l'environnement r5 précédent, ils n'en font pas une image déjà déployée.
4. Renouveler la lecture privée du registre, sans secret dans l'image, ses arguments,
   Git ou les logs. Les credentials ECR temporaires de la session précédente expirent.
5. Recréer un reçu d'endpoint privé contenant `id`, `image` par digest et `stop_at`.
   Copier `examples/config.example.json` vers `.local/config.json` et renseigner les
   emplacements de ce laboratoire. `stop_at` doit être futur et avec fuseau ; celui
   du reçu d'endpoint doit être identique. Fournir les secrets au processus par
   environnement privé (`RUNPOD_API_KEY`, `TYPESAFE_API_KEY`).
6. Démarrer seulement les tâches choisies explicitement :

```sh
python3 campaign/run_daily.py --execute
python3 campaign/publish_results.py --execute
python3 campaign/compare_daily.py --execute
```

`jev_intake.py --execute` reprend les contrôles FV-01/FV-02 déjà reçus. Ne pas écraser
les reçus existants pour cacher les quatre erreurs ; une relance forme un essai distinct.
Les scripts sont des harness de laboratoire, pas des services de production supervisés.
L'échéance du harness ne remplace pas un arrêt cloud indépendant.

Le mode standard V2 ne peut pas être déclaré complet si des modèles échouent, des sources
manquent dans les résultats ou la géométrie initiale est absente. Le champ
`full_pipeline_validated` reste faux jusqu'à cette qualification.

## Suivi local

Le serveur `jev-integration/server.py` conserve événements, cas, résultats et captures
privés sous `.local/typesafe-lab` (surcharge `FV_JEV_DATA_DIR`). Il écoute exclusivement
sur loopback et refuse les origines distantes. Via tunnel SSM/SSH, utiliser les mêmes
ports locaux qu'avant : 8766 (suivi), 54180 (site), 54181 (API). Les URLs sont inactives
quand la VM est arrêtée.

La page `index.html` présente l'inventaire et les résultats journaliers privés ; la
copier, avec les fichiers générés et médias autorisés, sous `dashboard/dist/daily/`
sur la VM. Ne jamais publier ce répertoire en site public. Le dashboard React contient
les comparaisons de briques et les captures. `npm run verify` valide son parcours
synthétique hors ligne ; cette vérification n'appelle aucun modèle.

## Arrêter

Suspendre les producteurs locaux, annuler les jobs actifs, mettre Runpod à min/max zéro,
vérifier la liste réelle des workers vide, puis arrêter EC2 et vérifier `stopped`.
Conserver les disques/archives pour reprendre. Ne pas terminer une VM ni supprimer son
volume pour obtenir un simple arrêt de nuit.

Un reçu annulé/échoué déjà présent bloque la reprise automatique. Archiver le précédent répertoire de tentative, conserver ses résultats, puis préparer une nouvelle tentative avec ses propres fichiers de progression et jobs ; ne pas supprimer les preuves de la tentative annulée. L’agrégateur exige les identifiants exacts de toutes les sources et des exécutions réussies.
