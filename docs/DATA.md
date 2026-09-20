# Données, collecte et droits

Le dépôt publie le code, les configurations sans secrets, les hashes de corpus et
les jugements structurés. Il ne republie pas les photos de presse, vidéos, PDF,
textes intégraux, poids, captures contenant ces médias, ni le rapport Jev utilisateur.
Les droits des sources restent ceux de leurs titulaires. Une ressource accessible
sur le Web n'est pas automatiquement redistribuable.

`manifests/corpus-public.json` décrit les 48 sources par identité, provenance et hash.
Il ne remplace pas `campaign/manifest.json` privé : son hash ne doit pas être présenté
comme celui du manifeste original. Le SHA original est conservé explicitement.

Les collecteurs racine couvrent documents officiels, aperçus NASA/Copernicus, recherche
Web, pages complémentaires, vidéos et produits optiques. `discover_sources.py` réutilise
le `ResearchBroker` de FireViewer ; `collect_optical_branch.py` réutilise son collecteur
Sentinel-2. `review_field_media.py` contient les décisions de la revue figée du corpus
Ribaute ; ses indices sont protégés par une assertion et ne constituent pas un outil
de tri automatique généralisable. La première sélection rejetée reste exclue.

Pour reprendre le corpus réel, restaurer l'archive privée approuvée sous `acquisition/`
et les reçus privés sous `campaign/`, vérifier les SHA puis `python3 campaign/freeze.py`.
La première sauvegarde de collecte contient 104 fichiers, environ 140 Mo ; les reçus de
sauvegarde, identifiants de stockage et résultats complets restent dans l'espace privé.
Ne pas retélécharger puis antidater des fichiers en prétendant reproduire leur disponibilité.

Les photos admises reproduisent des points de vue au sol ; plusieurs proviennent de
la presse ou des secours. Ce ne sont pas de vraies contributions FireViewer et leur
appareil de capture est souvent inconnu. Cette limite doit accompagner les résultats.

Les journées pauvres en sources restent pauvres dans les résultats. La suite doit
élargir les sources trouvables, vérifier les licences et la date des photos encore
ambiguës ; jamais remplir une journée avec des vues aériennes comme faux téléphones.
