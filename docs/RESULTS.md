# Résultats et limites — campagne du 20 septembre 2026

**Aucune comparaison complète des journées n'est terminée. Aucun meilleur pipeline
n'est identifié.** Le travail a été suspendu avant la fin du premier job sur le
worker dont l'image r5 était vérifiée ; ce job a été annulé.

| Jour local 2025 | Images au sol admises | Rapports officiels |
|---|---:|---:|
| 5 août | 15 | 7 |
| 6 août | 7 | 7 |
| 7 août | 3 | 3 |
| 8 août | 1 | 3 |
| 9 août | 0 | 2 |

Total : 48 entrées (26 visuelles et 22 rapports), sans plafond journalier.
Les 26 images comprennent 21 scènes positives et 5 cas difficiles ; ce tri de corpus
n'est pas une vérité terrain de benchmark. Quatorze autres images au sol restent
exclues du regroupement journalier faute de date suffisante.
Trois rapports scannés ont été transcrits par Tesseract ; l'OCR n'est pas validé humainement.

## Jev réel

- FV-01 : 48 réponses acceptées sur 48 ; 38 « vegetation_fire », 10 « indeterminate ».
- FV-02 : 44 réponses acceptées sur 48 ; 32 reprises tierces, 10 informations
  insuffisantes, 2 conseils. Quatre erreurs `ValueError` du validateur client.
- Les réponses originales des quatre erreurs n'ont pas été conservées : leur cause
  ne peut donc pas être attribuée avec certitude au modèle. Une relance diagnostique
  isolée a réussi ; elle n'efface pas le reçu d'erreur initial.
- Coût des appels acceptés : 0,003578988 USD, calculé à partir des tokens reçus et du
  tarif configuré de 0,042 USD/million de tokens d'entrée. Coût des erreurs non mesuré ;
  la relance diagnostique (0,000042924 USD) n'est pas incluse dans ce total.
- LOC-02 / LOC-04 : harness préparé, aucune journée complète validée exécutée.
  Les huit autres contrats sont définis et testés hors ligne, sans campagne réelle.

Les sorties structurées expurgées sont dans `results/2026-09-20/`. Les textes intégraux
et reçus privés restent dans l'archive locale du laboratoire.

## Bonsaï 2 réel

`prism-ml/Ternary-Bonsai-2-27B-gguf`, PTQ1_0 : 5 946 648 928 octets de poids,
plus 629 246 976 octets de projecteur Q8. Révisions et hashes : `manifests/bonsai2.lock.json`.

| Sonde GPU | Chargement | Inférence | VRAM maximale échantillonnée |
|---|---:|---:|---:|
| Rapport officiel | 3 896 ms | 3 780,872 ms | 8 112 MiB |
| Photo au sol | 3 746,29 ms | 5 358,866 ms | 8 166 MiB |

Mesures du périphérique entier par `nvidia-smi`, toutes les secondes ; elles peuvent
manquer un pic court et inclure d'autres processus. Ce sont deux sondes d'intégration
avec candidats contrôlés, pas une mesure de précision ni du pipeline complet.
Qwen3.5-9B a utilisé environ 18,25 GiB dans un lot partiel : le pipeline entier ne
se réduit donc pas aux quelque 8 GiB mesurés pour le juge.

## Branches et réparations

Deux paires Sentinel-2 du 4 au 7 août ont été réellement traitées à 20/40 m. Les jours
8/9 réutilisent l'observation du 7, sans prétendre disposer d'une nouvelle acquisition.
Pas de paire admissible les 5/6. Les aperçus NASA/Copernicus restent des aperçus.
L'absence d'accès FIRMS et une réponse EFFIS vide ne signifient pas absence de feu.

Des lots r4 ont exécuté D-FINE standard, RT-DETR et Florence ; le contrat Qwen a refusé
une réponse entourée de balises Markdown. r5 normalise une seule enveloppe JSON exacte,
tout en refusant texte autour et valeurs invalides. Ses tests passent, mais sa validation
GPU quotidienne reste à terminer. D-FINE COCO ne possède pas de classe feu/fumée.

Le backend de laboratoire n'avait pas d'incident ni de périmètre initial admissible.
La fusion spatiale reste `awaiting_spatial_initialization`. Aucune géométrie n'a été
fabriquée pour masquer ce manque. La recherche complète de sources, tous les providers
et la chaîne site → backend → reconstruction restent à qualifier ensemble.
