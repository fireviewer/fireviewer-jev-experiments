# Secrets et publication

Les clés sont fournies au serveur par environnement privé ou formulaire local en mémoire.
Le client Web ne conserve pas la clé dans le stockage du navigateur. Les sources de
modèles et paquets sont épinglées ; les URLs signées de transport sont remplacées par
les hashes dans les reçus du lanceur. Les reçus complets restent privés malgré cela.

Les fichiers `.local/`, `.env*`, caches, jobs, médias et archives sont ignorés. Cela
ne remplace pas le contrôle du staging : chaque publication doit vérifier `git diff
--cached`, le contenu des fichiers ajoutés et l'historique des commits à pousser.

Avant cette publication : Gitleaks avec valeurs masquées et recherche en mémoire des
valeurs de credentials locaux connus. Les rapports publics ne contiennent que nombres
et périmètre des contrôles ; les éventuels rapports détaillés restent privés.
Un scan sans détection est une vérification de portée définie, pas une garantie absolue.

Pour répéter le contrôle :

```sh
gitleaks dir . --redact --no-banner
gitleaks git . --redact --no-banner --log-opts="--all"
```

Ne pas joindre les fichiers d'authentification à un ticket. En cas de secret commis,
révoquer/renouveler la clé, nettoyer l'historique non publié, puis rescanner avant push.
Les dépôts privés existants conservent leur visibilité. Seul ce dépôt d'expérimentations
est créé public ; cette publication n'autorise pas celle des données tierces.
