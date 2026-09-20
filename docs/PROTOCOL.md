# Protocole des comparaisons quotidiennes

L'unité métier est l'incendie, le jour local et l'état connu au début de ce jour.
Une journée peut manquer de certaines catégories. La collecte cherche largement
les sources disponibles, sans quota arbitraire de quelques images et sans test
de charge artificiel d'utilisateurs. Une catégorie absente reste explicitement absente.

1. Collecter rapports officiels, sources NASA/Copernicus, photos et vidéos pertinentes,
   textes, périmètres et statistiques disponibles ; conserver provenance et droits.
2. Distinguer capture, publication, acquisition et disponibilité historique. Dédupliquer
   les fichiers et regrouper reprises, photos du même reportage et frames d'une vidéo.
3. Figer le corpus, la configuration, l'état antérieur et le lot d'arrivée par SHA-256.
   Garder les exclusions motivées et les sources dont le jour reste indéterminé.
4. Exécuter réellement toutes les entrées admises avec la même image GPU par digest.
   Les fenêtres techniques de quatre sources n'amputent jamais une journée : agréger
   toutes les fenêtres avant toute comparaison quotidienne.
5. Comparer la référence avec une seule brique Jev à la fois. Les sorties visuelles
   sont partagées à l'identique ; les avis Jev ne réécrivent pas les observations brutes.
6. Évaluer erreurs, abstentions, latence, tokens, coûts et couverture ; faire annoter
   les cas indépendamment avant de comparer précision, rappel ou calibration.
7. Comparer les états successifs et périmètres seulement avec des états initiaux et
   preuves géométriques admissibles. Garder séparés observé, inféré et simulé.

L'image réellement servie par le worker doit égaler le digest demandé. Un job exécuté
par un ancien worker après changement de version est exclu. Les relances conservent
les reçus d'erreur et utilisent un répertoire distinct si l'image ou le corpus change.
Aucun résultat partiel, annulé ou invalide ne devient une journée validée.

Pour un remplacement, importer les reçus de la brique existante, mêmes entrées et
mêmes états. En l'absence de cette référence, nommer l'expérience « ajout d'un contrôle
optionnel » et ne pas attribuer de gain au remplacement d'un outil inexistant.

Le corpus Ribaute reste une étude rétrospective : certains jours de capture sont
inférés du contexte du reportage ; l'heure exacte de disponibilité historique n'est
pas vérifiée partout. Une étude sans fuite temporelle exige de résoudre ces cas.
Le découpage entraînement/évaluation se fait par incident et groupe de provenance,
jamais par frame ou duplicata isolé.
