# Mealie Personal Edition — maintenance du fork

Ce dépôt est un fork de [mealie-recipes/mealie](https://github.com/mealie-recipes/mealie) (licence AGPL-3.0).
Il ajoute un gestionnaire culinaire personnel : personnes et restrictions alimentaires, événements,
plans de courses, stocks, inspirations, assistant IA.

Ce fichier explique comment le fork est construit pour rester facile à mettre à jour.

## Règle de construction : tout est additif

- Le code du fork vit dans ses propres dossiers. Aucune table, aucun schéma ni aucun écran de Mealie n'est modifié.
- Les tables du fork portent toutes le préfixe `pe_`.
- Les migrations du fork ont leur propre historique et leur propre table de version
  (`alembic_version_personal`). L'historique de migrations de Mealie reste identique à celui de l'amont.

| Quoi | Où |
|---|---|
| Modèles | `mealie/db/models/personal/` |
| Migrations | `mealie/alembic_personal/`, pilotées par `mealie/db/personal_migrations.py` |
| Schémas d'API | `mealie/schema/personal/` |
| Dépôts | `mealie/repos/personal/` |
| Services et moteur de calcul | `mealie/services/personal/` (moteur pur dans `engine/`) |
| Routes | `mealie/routes/personal/` |
| Tests | `tests/unit_tests/personal_tests/`, `tests/integration_tests/personal_tests/` |
| Client API | `frontend/app/lib/api/user/personal.ts` |
| Pages | `frontend/app/pages/{hub,people,dietary,events,shopping-plans,pantry,inspirations,assistant}/` |
| Apparence « verre liquide » | `frontend/app/assets/personal/liquid-glass.css`, chargée par `frontend/app/plugins/personal-theme.client.ts` |
| Composants et composables | `frontend/app/components/Domain/{Personal,MealEvent,ShoppingPlan,Pantry,Inspiration,Assistant}/`, `frontend/app/composables/personal/` |
| Textes de l'interface | `frontend/app/lang/personal/<langue>/*.json`, chargés par `frontend/app/plugins/personal-i18n.ts` |
| Déploiement NAS | `deploy/nas/` |
| Image | `.github/workflows/personal-image.yml` |

## Les cinq fichiers de Mealie que le fork modifie

Ce sont les seuls endroits où une mise à jour amont peut créer un conflit. Chaque modification tient en
quelques lignes.

| Fichier | Modification | Pourquoi |
|---|---|---|
| `mealie/db/init_db.py` | import + `personal_migrations.upgrade()` après la migration de Mealie | Créer et mettre à jour les tables `pe_` au démarrage |
| `mealie/services/backups_v2/alchemy_exporter.py` | import, `personal_migrations.upgrade_for_restore(db_dump)` dans `restore`, `register_backup_columns(AlchemyExporter)` en fin de fichier | Recréer les tables `pe_` avant qu'une restauration y remette ses lignes ; restaurer les dates du fork |
| `mealie/repos/repository_factory.py` | `class AllRepositories(PersonalRepositories)` + import | Exposer les dépôts du fork |
| `mealie/routes/__init__.py` | import + `router.include_router(personal.router)` | Brancher les routes du fork |
| `frontend/app/components/Layout/DefaultLayout.vue` | trois composables, trois `...spread` et `<PersonalBottomNav />` | Entrées de menu, page d'accueil, barre d'onglets sur téléphone |

Fichiers générés propres au fork, à ne pas modifier à la main : `mealie/schema/personal/__init__.py` et
`frontend/app/lib/api/types/personal.ts`.

## Apparence

Le style « verre liquide » tient dans une seule feuille de style, `liquid-glass.css`. Elle ne modifie
aucun composant de Mealie : chaque règle est placée sous la classe `pe-glass`, posée sur la page par le
greffon `personal-theme.client.ts`. Retirer cette classe redonne l'apparence d'origine ; l'interrupteur
« Effet verre » de la page « Aujourd'hui » fait exactement cela.

- Le flou réel est réservé aux barres, menus et dialogues. Les cartes de contenu sont translucides sans
  flou, pour que les longues listes restent fluides sur un téléphone.
- Les réglages système « réduire la transparence » et « réduire les animations » sont respectés.
- La barre d'onglets flottante s'efface sur les pages natives qui ont déjà une barre en bas d'écran
  (la liste de courses et son « Ajouter un article »).

Après une mise à jour amont de Vuetify, vérifier visuellement les pages natives : la feuille cible des
classes de Vuetify (`.v-card`, `.v-app-bar`, `.v-navigation-drawer`, `.v-dialog`, `.v-menu`, `.v-btn`).

## Branches

`mealie-next` est la branche principale du fork et contient le fork. Le travail se fait sur une branche
dédiée, fusionnée dans `mealie-next` une fois les contrôles passés.

## Mettre à jour depuis l'amont

Le fork suit les **versions publiées** de Mealie (tags `vX.Y.Z`), pas chaque commit de `mealie-next`.

```bash
git remote add upstream https://github.com/mealie-recipes/mealie.git
```

```bash
git fetch upstream --tags
```

```bash
git merge v3.32.0
```

Après la fusion :

1. Résoudre les conflits. Ils ne peuvent toucher que les cinq fichiers ci-dessus : garder la version
   amont et réappliquer les quelques lignes du tableau.
2. Régénérer les fichiers générés, puis ne garder que ceux du fork si l'outil en reformate d'autres :
   `mise run dev:generate`.
3. Lancer les contrôles : `mise run py:check` et `mise run ui:check`.
4. Lancer les tests du fork sur PostgreSQL (voir plus bas). C'est la base de production.
5. Construire l'image `<version amont>-pe.<n>` et la déployer avec `deploy/nas/upgrade.sh`.

### Ce qu'il faut vérifier quand l'amont change

| Si l'amont modifie… | Vérifier |
|---|---|
| `ShoppingListService` ou les schémas des listes de courses | `mealie/services/personal/shopping_plan_service.py` et `pantry_service.py`, qui écrivent des articles natifs |
| `OpenAIService` (`_get_provider`, `get_client`) | `mealie/services/personal/assistant_service.py` |
| `RecipeService` (`create_one`, `duplicate_one`, `update_one`) | `inspiration_service.py` et `proposal_service.py` |
| Le schéma des recettes et des ingrédients | `mealie/services/personal/recipe_needs.py` |
| La sauvegarde (`alchemy_exporter.py`) | Les deux points d'accroche et `tests/integration_tests/personal_tests/test_backup_restore.py` |
| Les tables `groups`, `households`, `recipes`, `ingredient_foods`, `ingredient_units`, `tools`, `shopping_lists` | Les clés étrangères des tables `pe_` y pointent |

## Migrations du fork

- Ne jamais créer de migration du fork avec `mise run py:migrate` : cette commande écrit dans
  l'historique de Mealie.
- Créer une migration du fork :

```bash
uv run python -c "from mealie.db import personal_migrations as m; m.revision('description')"
```

- Toute clé étrangère d'une table `pe_` vers une table de Mealie porte une règle de suppression
  (`CASCADE` ou `SET NULL`). Sans elle, PostgreSQL refuse la suppression native d'une recette, d'un
  aliment ou d'une liste de courses. `tests/integration_tests/personal_tests/test_native_deletions.py`
  le vérifie.
- Les valeurs imbriquées (listes, dictionnaires) sont stockées en texte JSON (`JSONText`), et toute
  nouvelle colonne de date doit être ajoutée à `DATETIME_COLUMNS` ou `DATE_COLUMNS` dans
  `mealie/db/personal_migrations.py`. Sinon la sauvegarde native ne sait pas les restaurer.

## Tests

```bash
uv run pytest tests/unit_tests/personal_tests tests/integration_tests/personal_tests
```

Sur PostgreSQL (obligatoire avant un déploiement — SQLite n'applique pas les clés étrangères) :

```bash
DB_ENGINE=postgres POSTGRES_SERVER=localhost POSTGRES_USER=mealie POSTGRES_PASSWORD=mealie POSTGRES_DB=mealie uv run pytest tests/unit_tests/personal_tests tests/integration_tests/personal_tests -n 4 --dist loadfile
```

## Base de données prise en charge

Le fork est prévu pour **PostgreSQL**. Il fonctionne sur SQLite pour le développement, mais SQLite
n'applique pas les clés étrangères : supprimer un aliment y laisse des lignes orphelines dans les
tables `pe_`.

## Revenir à Mealie d'origine

Le fork ne change rien aux tables ni à l'historique de migrations de Mealie. Pour l'abandonner :

```bash
docker compose exec mealie python -c "from mealie.db import personal_migrations as m; m.downgrade()"
```

Cette commande supprime toutes les tables `pe_`. La base est alors une base Mealie ordinaire, que
l'image officielle de la même version peut ouvrir.

## Licence

Mealie est distribué sous licence AGPL-3.0, et ce fork aussi. Le fichier `LICENSE` et les mentions
d'auteur sont conservés. Le code source modifié est ce dépôt : il doit rester accessible à toute
personne qui utilise l'instance par le réseau.
