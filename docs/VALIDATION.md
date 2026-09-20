# Validation de la publication

Contrôles exécutés avant arrêt de la VM, dans l'image r5 existante avec les nouveaux
répertoires de sources montés : **70 tests ciblés réussis** (62 contrats, Bonsaï,
normalisation JSON, orchestrateur ; 8 adaptateurs et juge historique/nouveau).
Cela valide le code ciblé dans cet environnement, pas une nouvelle inférence GPU.

Noyau Jev : **30 tests réussis**, dont appels HTTP locaux, protection des clés,
contrats de douze briques, projections textuelles, règles préalables, erreurs et contrôle des reçus quotidiens.
Dashboard : `npm ci` puis build Vite réussis ; aucun appel TypeSafe/GPU pendant ces tests.
Les avertissements `use client` de la dépendance d'icônes ne bloquent pas le build Vite.

Le contrôle navigateur et le contrôle des secrets ont leur reçu dans `results/publication/`.
Les CI des dépôts composants testent leurs artefacts CPU ; elles ne remplacent ni les
sondes GPU ni le comparatif journalier. Les versions des dépendances CPU historiques
ne sont pas un environnement d'inférence : le runtime GPU exige Transformers 5.14.1.

Dette héritée de l'image r5 : `pip check` signale les métadonnées romatch pour loguru,
opencv-python et poselib. Les imports d'inférence vérifiés fonctionnent avec OpenCV
headless ; ce constat ne transforme pas `pip check` en PASS.

Restent à exécuter : nouvelle image à partir des commits publiés, première journée
entière sans erreur de modèle, raccordement des états initiaux et chaîne site/backend,
comparaisons Jev post-vision, annotations indépendantes et mesure qualitative.

## Paquets entre dépôts

Le nouveau contrat est publié en source en version 0.1.2. Les métadonnées de
géolocalisation, collecte et supervision ont été alignées sur cette version, sans
modifier leurs règles métier. Leurs commits, ceux du runtime et de l'orchestrateur
sont verrouillés par `ci.json` et le manifeste global. La construction CPU applique
les mêmes hashes de wheels que les tests ; elle ne réutilise pas les anciennes
wheels incompatibles avec ce contrat. Aucune release existante n'est remplacée.
