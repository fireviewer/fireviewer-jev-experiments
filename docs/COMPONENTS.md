# Contrats Jev

Modèle épinglé : `jev-1.13.0`. Les critères complets et champs admis sont dans
`jev-integration/components.py` ; son `REVISION` et le hash du contenu identifient
la version expérimentale. Chaque appel sélectionne exactement une ligne ci-dessous.

| ID | Jugement textuel | Précondition / limite |
|---|---|---|
| FV-01 | Sujet : végétation, autre feu, prévention, rétrospective, indéterminé | Aucun rejet d'image sur ce seul jugement |
| FV-02 | Témoignage, reprise, simulation, conseil, discours insuffisant | Pas une vérification de vérité |
| FV-03 | Deux descriptions évoquent-elles le même dossier ? | Reçu Python de compatibilité spatiale et temporelle |
| FV-04 | Message de complément adapté | Champs manquants calculés ; messages préécrits uniquement |
| DS-01 | Type de prise de vue décrit | Métadonnées textuelles, pas inspection des pixels |
| DS-02 | Lacunes du texte de licence | Pas une autorisation juridique d'utilisation |
| DS-03 | Orientation d'un échec technique ambigu | Seulement après absence de règle déterministe applicable |
| DS-04 | Motif du désaccord pour la revue | Assistance à la file humaine |
| LOC-01 | Lieu le plus cohérent parmi des candidats | Géocodeur externe ; identifiant existant ou abstention |
| LOC-02 | Contradictions entre déclarations et références | Contexte textuel sourcé, aucune distance calculée par Jev |
| LOC-03 | Maturité documentaire du dossier | Revue géométrique/humaine conservée |
| LOC-04 | Prudence des affirmations avant publication | Jamais une autorisation automatique de publication |

Les primitives `Choice`, `Noul` et leurs distributions sont validées côté client.
Les valeurs manquantes, inconnues ou invalides sont des erreurs/abstentions, jamais
des succès imputés. Les données auxiliaires, labels humains, secrets et pixels ne
font pas partie de la projection textuelle envoyée au modèle.

Le rapport d'exploration fourni par l'utilisateur a servi à définir ce périmètre.
Il n'est pas redistribué. Le Pilote B de 600 textes n'a pas été exécuté ; les 48
sources de la campagne ne constituent pas une reproduction de ce pilote.
