# Mealie Personal Edition — Audit et plan technique

État : **réalisé** (voir §6). Ce document garde l'audit et la conception d'origine ; les écarts entre le plan et la réalisation sont listés en §6.
Base auditée : `mealie-next` au commit `c5c68a2` (15 novembre 2026).

---

## 1. Phase A — Audit

### 1.1 Branches

| Référence | Commit / version | Constat |
|---|---|---|
| Stable amont | tag `v3.31.0` | Dernière version publiée. |
| Développement amont `mealie-next` | `c5c68a2` | 17 fichiers d'écart avec `v3.31.0` (hors traductions et lockfiles), **aucune différence de schéma ni de migration**. |
| Fork `Haswell119/mealie` | `c5c68a2` | Strictement identique à l'amont. Aucun tag dans le fork. |

Conséquence : partir de `mealie-next` ou de `v3.31.0` est équivalent aujourd'hui. Je recommande de **suivre les tags de version amont** (stables) et non chaque commit de `mealie-next`.

### 1.2 Architecture réelle

- Backend : Python 3.14, FastAPI, SQLAlchemy 2, Alembic (65 migrations), Pydantic. Motif contrôleur → service → dépôt, tout est cloisonné par **groupe** et **foyer**.
- Frontend : Nuxt 4, Vue 3, Vuetify, TypeScript. Types API **générés** depuis les schémas Pydantic (`mise run dev:generate`).
- Les migrations sont appliquées au démarrage par `mealie/db/init_db.py` avec `command.upgrade(cfg, "head")`.
- SQLite n'active pas `PRAGMA foreign_keys` : les cascades SQL ne sont pas fiables en test, il faut nettoyer côté service.

### 1.3 Fonctionnalités natives réutilisables

| Besoin du cahier des charges | Existant dans Mealie | Fichiers |
|---|---|---|
| Recettes structurées | Ingrédients `quantité / unité / aliment / note`, sous-recettes, ustensiles, portions (`recipe_servings`), rendement | `mealie/db/models/recipe/` |
| Mise à l'échelle | Facteur d'échelle côté recette et côté planning (`GroupMealPlan.recipe_scale`) | `frontend/app/composables/recipes/use-scaled-amount.ts`, `use-mealplan-scale.ts` |
| Conversions d'unités | `standard_quantity` / `standard_unit` sur les unités + `pint`. Masse↔masse et volume↔volume. **Pas de densité** (pas de g↔ml) | `mealie/services/parser_services/parser_utils/unit_utils.py` |
| Listes de courses | Articles `aliment / unité / quantité / étiquette / coché`, fusion des aliments identiques à unités compatibles, tri par étiquette | `mealie/services/household_services/shopping_lists.py` |
| Provenance | `ShoppingListItemRecipeReference` (recette, quantité, échelle, note) | `mealie/db/models/household/shopping_list.py` |
| Courses depuis plusieurs recettes / le planning | `POST /shopping/lists/{id}/recipe` en lot, bouton « tout ajouter » du planning | `controller_shopping_lists.py`, `pages/household/mealplan/planner.vue` |
| Stock (partiel) | Aliment « en stock » **booléen** par foyer, ustensiles disponibles | `households_to_ingredient_foods`, `households_to_tools` |
| Suggestions selon le stock | Recherche de recettes par aliments/ustensiles disponibles, avec substitutions | `mealie/repos/_recipe_suggestions.py`, page `recipes/finder` |
| Substitutions | Au niveau de l'aliment et de la ligne d'ingrédient | `ingredient_foods_substitutions`, `recipes_ingredients_substitutions` |
| Fournisseur IA | Fournisseurs **compatibles OpenAI** configurables par groupe : `base_url`, clé, modèle, en-têtes, paramètres, délai. Prompts surchargeables. Clé en écriture seule dans l'API | `mealie/db/models/group/ai_providers.py`, `mealie/services/openai/openai.py` |
| IA existante | Création de recette depuis texte / image / vidéo, analyse d'ingrédients, traduction, enrichissement des étapes | `mealie/services/openai/prompts/` |
| Extension sans migration | Champs `extras` clé/valeur sur recettes, aliments, listes et articles | `mealie/db/models/recipe/api_extras.py` |
| Déploiement | Image unique, PostgreSQL, lecture des secrets dans `/run/secrets`, sauvegardes v2 | `docker/`, `mealie/core/settings/settings.py`, `mealie/services/backups_v2/` |

### 1.4 Ce qui manque

1. Personnes sans compte, restrictions, portées, sévérité, consentement.
2. État de vérification des aliments par restriction.
3. Événements, menu multi-plats, variantes, portions par variante.
4. Moteur de conformité déterministe.
5. Distinction « quantité nécessaire » / « quantité à acheter », conditionnements, restes.
6. Stock **quantifié**.
7. Inspirations et workflow vers recette validée.
8. Assistant IA avec appels de fonctions et validation explicite.

### 1.5 Points d'attention découverts

- **Régénération des courses.** `can_merge` refuse toute fusion avec un article coché. Ré-ajouter une recette crée donc un nouvel article non coché à côté de l'article déjà acheté. L'exigence « recalculer sans réintroduire les achats ni perdre les ajustements manuels » **ne peut pas** reposer sur l'ajout natif : il faut un algorithme de réconciliation dédié (§2.5).
- **Identifiants d'ingrédients instables.** Les lignes `recipes_ingredients` sont détruites et recréées à chaque enregistrement de recette. Toute donnée liée à une ligne doit utiliser `reference_id` (UUID stable), jamais `id`.
- **Collision de nom.** « Events » désigne déjà les notifications (`household/events.py`, `event_bus_service`). Le nouveau domaine s'appellera `meal_event` dans le code, « Événements » dans l'interface.
- **Calculs en `Float`.** Le moteur natif additionne des flottants. Le nouveau moteur calculera en `Decimal` et n'arrondira qu'en sortie.
- **Clé IA en base.** `ai_providers.api_key` est stockée en clair dans PostgreSQL, donc présente dans les sauvegardes. Les sauvegardes doivent être chiffrées.
- **Traductions.** Crowdin réécrit tous les fichiers de langue presque chaque jour. Modifier `fr-FR.json` produirait un conflit à chaque synchronisation.

### 1.6 Risques de maintenance du fork

| Risque | Probabilité | Parade |
|---|---|---|
| Conflit de migrations Alembic (deux têtes) | Certaine sans parade | Branche Alembic indépendante `personal` (§2.1) |
| Conflits dans les fichiers amont modifiés | Moyenne | Code du fork dans des modules séparés, liste fermée de points de contact (§2.1) |
| Conflits de traductions | Certaine sans parade | Chaînes du fork dans des fichiers séparés |
| Changement du service de courses amont | Moyenne | Passer uniquement par l'API publique du service + tests de compatibilité |
| Changement du client IA amont | Faible à moyenne | Couche d'adaptation unique `AssistantService` |
| Renommage de tables amont référencées | Faible | Clés étrangères vers des tables cœur stables uniquement |

---

## 2. Phase B — Conception

### 2.1 Stratégie de fork

**Branches.** `mealie-next` est la branche principale du fork et contient le fork (le plan initial la gardait en miroir de l'amont). À chaque tag amont : fusion du tag, tests complets, nouvelle image.

**Règle d'or : additif uniquement.** Aucune colonne ajoutée aux tables amont, aucune table amont modifiée. Tables du fork préfixées `pe_`.

**Emplacement du code.**

```
mealie/db/models/personal/       mealie/schema/personal/
mealie/repos/personal/           mealie/services/personal/
mealie/routes/personal/          mealie/alembic/versions_personal/
frontend/app/components/Domain/{Person,MealEvent,Inspiration,Pantry,Assistant}/
frontend/app/pages/{people,events,inspirations,pantry,assistant}/
frontend/app/lang/personal/      tests/**/personal_tests/
```

**Points de contact avec les fichiers amont (liste fermée, documentée dans `FORK.md`).**

| Fichier amont | Modification |
|---|---|
| `mealie/db/init_db.py` | `"head"` → `"heads"` (une ligne) |
| `mealie/alembic/env.py` ou `alembic.ini` | Ajout de `versions_personal` aux emplacements de versions |
| `mealie/db/models/_all_models.py` | Import des modèles du fork |
| `mealie/repos/repository_factory.py` | Dépôts du fork |
| `mealie/routes/__init__.py` | Inclusion du routeur du fork |
| `frontend/app/components/Layout/DefaultLayout.vue` | Entrées de navigation |
| `frontend/nuxt.config.ts` | Chargement des chaînes du fork |

**Migrations.** Branche Alembic indépendante : `branch_labels = ("personal",)`, `down_revision = None`, `depends_on = <révision cœur de v3.31.0>`. Les migrations amont et celles du fork n'ont jamais la même tête : aucune réécriture d'historique lors des mises à jour. Chaque migration du fork a un `downgrade` testé sur SQLite et PostgreSQL.

**Licence AGPL-3.0.** Conserver `LICENSE` et les mentions d'auteur, signaler que le logiciel est modifié, et proposer le code source modifié à tout utilisateur qui accède à l'instance par le réseau (lien « Source » vers le dépôt du fork dans la page À propos). Ce point n'est pas un avis juridique.

### 2.2 Modèle de données

Toutes les tables portent `group_id` et, quand c'est pertinent, `household_id`.

**Personnes et restrictions**

| Table | Colonnes principales |
|---|---|
| `pe_persons` | `display_name`, `appetite` (SMALL / NORMAL / LARGE), `notes`, `linked_user_id` (nul pour un invité), `consent_given_at`, `consent_note` |
| `pe_dietary_restrictions` | `key` (gluten, meat, fish, …), `name`, `kind` (MEDICAL / ALLERGY / INTOLERANCE / ETHICAL / PREFERENCE) |
| `pe_person_restrictions` | `person_id`, `restriction_id`, `severity` (STRICT / MODERATE / PREFERENCE), `default_scope` (INDIVIDUAL / ENTIRE_MEAL / ENTIRE_PREPARATION), `applies_when_cooking`, `notes` |
| `pe_person_food_preferences` | `person_id`, `food_id`, `kind` (LIKE / DISLIKE) |

Une fiche sans consentement enregistré ne peut pas contenir de restriction ni de note. La suppression d'une personne efface toutes ses données liées.

**Vérification des aliments et ustensiles**

| Table | Colonnes principales |
|---|---|
| `pe_food_restriction_status` | `food_id`, `restriction_id`, `status` (VERIFIED / UNVERIFIED / INCOMPATIBLE), `source` (MANUAL / RULE / AI_SUGGESTION), `reason`, `verified_by`, `verified_at` |
| `pe_tool_restriction_status` | `tool_id`, `restriction_id`, `requires_check`, `reason` |

Invariants, imposés par le service **et** par une contrainte SQL :

- Absence de ligne = `UNVERIFIED`.
- `VERIFIED` exige `source = MANUAL` et `verified_by` non nul. Une règle ou l'IA ne peuvent produire que `INCOMPATIBLE` ou `UNVERIFIED`.
- Un ingrédient sans aliment lié (texte libre) est toujours `UNVERIFIED`.

Règles déterministes initiales pour le gluten : blé, froment, épeautre, kamut, orge, seigle, triticale, malt, seitan, boulgour, semoule, couscous et dérivés → `INCOMPATIBLE`. Avoine, sauces, bouillons, charcuteries et produits transformés → `UNVERIFIED` avec motif « vérification de l'étiquette requise ». La liste est une donnée versionnée, pas du code.

**Événements**

| Table | Colonnes principales |
|---|---|
| `pe_meal_events` | `name`, `starts_at`, `location`, `cook_person_id`, `status` (DRAFT / PLANNED / DONE), `leftover_portions`, `notes`, `shopping_list_id` |
| `pe_meal_event_guests` | `event_id`, `person_id`, `attending`, `appetite_override` |
| `pe_meal_event_restriction_overrides` | `event_id`, `menu_item_id` (nul = tout l'événement), `person_restriction_id`, `scope`, `reason`, `created_by` |
| `pe_meal_event_menu_items` | `event_id`, `course` (STARTER / MAIN / DESSERT / OTHER), `position` |
| `pe_meal_event_menu_variants` | `menu_item_id`, `recipe_id`, `label`, `portions_override` |
| `pe_meal_event_requirements` | Grand livre des besoins : `event_id`, `food_id`, `unit_id`, `variant_id`, `qty_needed`, `qty_from_stock`, `qty_to_buy`, `projected_qty`, `shopping_list_item_id` |
| `pe_meal_event_history` | `event_id`, `at`, `user_id`, `action`, `payload` |

Une **variante est une recette** (duplication native puis adaptation validée). Ce choix évite un système de substitutions à la volée et garde les quantités dans les données structurées. Les substitutions par ligne, indexées par `reference_id`, sont reportées après le MVP.

**Phase E** : `pe_pantry_items` (quantité, unité, `confirmed_usable_at`, péremption) et `pe_food_packagings` (taille de conditionnement).
**Inspirations** : `pe_inspirations` (`kind`, `url`, `text`, pièce jointe, `status` INSPIRATION / DRAFT / VALIDATED, `draft` JSON au format `RecipeDraft`, `recipe_id`).

### 2.3 Résolution des portées

Ordre de priorité, du plus spécifique au plus général :

1. Surcharge sur une préparation (`menu_item_id` renseigné).
2. Surcharge sur l'événement.
3. Défaut de la personne.
4. Défaut du profil du cuisinier (`applies_when_cooking`).

Règles :

- Sans surcharge, **la portée la plus stricte l'emporte**.
- Assouplir une restriction `STRICT` exige une action explicite de l'utilisateur, un motif, et une entrée dans l'historique.
- Aucune voie d'API ouverte à l'IA ne peut créer de surcharge.

Résultat pour l'exemple métier : le gluten du propriétaire s'applique à toutes les variantes de tous les plats ; viande et poisson ne s'appliquent qu'à la portion de l'invité végétarien.

### 2.4 Moteur de conformité et de portions

Fonctions pures, sans base ni réseau, donc testables unitairement.

- **Portions.** `portions(variante) = Σ facteur d'appétit des convives présents affectés à la variante + restes`. `échelle = portions / recipe_servings`. Une recette sans `recipe_servings` bloque le calcul avec un message explicite, jamais de valeur devinée.
- **Affectation.** Chaque convive reçoit la première variante compatible avec ses restrictions `INDIVIDUAL`. Un convive sans variante compatible produit une erreur visible.
- **Conformité.** Pour chaque variante et chaque restriction applicable : parcours des ingrédients (sous-recettes incluses) et des ustensiles. Sortie : `COMPATIBLE`, `UNVERIFIED` (liste des éléments à vérifier), `INCOMPATIBLE` (ingrédient et motif). Pour `ENTIRE_PREPARATION`, une liste de contrôle de contamination croisée est ajoutée (ustensiles à vérifier, huile de friture, surfaces).
- Un menu contenant du `UNVERIFIED` peut être validé, mais les éléments restent signalés partout. Un `INCOMPATIBLE` bloque la validation tant qu'il n'est pas corrigé ou explicitement surchargé.

### 2.5 Génération et réconciliation des courses

1. **Besoins.** Pour chaque variante : réutilisation de `ShoppingListService.get_shopping_list_items_from_recipe` (sous-recettes et échelle natives).
2. **Agrégation.** Fusion par aliment avec `merge_quantity_and_unit`. Unités non convertibles : lignes séparées, jamais d'addition approximative.
3. **Stock** (phase E). Déduction du stock **confirmé utilisable** uniquement.
4. **Achat.** Arrondi au conditionnement supérieur si un conditionnement est défini.
5. **Grand livre.** Écriture dans `pe_meal_event_requirements`.
6. **Projection** dans la liste native via les services natifs. La provenance native (`recipe_references`) est conservée.

Réconciliation lors d'un recalcul, par ligne du grand livre :

| Situation | Action |
|---|---|
| Article coché | Jamais modifié ni recréé. Sa quantité compte comme couverte. Seul un manque crée un article complémentaire. |
| Article non coché, quantité ≠ `projected_qty` | L'écart est un ajustement manuel. Il est conservé et réappliqué. |
| Article supprimé par l'utilisateur | Non recréé, sauf demande explicite. |
| Article ajouté à la main | Jamais touché. |

Exemple du cahier des charges : A 400 g + B 300 g → besoin 700 g ; stock confirmé 200 g → achat 500 g.

### 2.6 API

Préfixe `/api/households/…`, contrôleurs dérivés de `BaseCrudController`.

```
/persons, /persons/{id}/restrictions, /persons/{id}/food-preferences
/dietary/restrictions, /dietary/foods/{food_id}/status
/meal-events, /meal-events/{id}/guests, /meal-events/{id}/menu
/meal-events/{id}/constraints         (lecture : contraintes consolidées)
/meal-events/{id}/compliance          (lecture : rapport de conformité)
/meal-events/{id}/portions            (lecture : portions par variante)
/meal-events/{id}/shopping/preview    (lecture : besoin / stock / achat)
/meal-events/{id}/shopping/apply      (écriture explicite)
/inspirations, /pantry, /assistant    (phases ultérieures)
```

### 2.7 Parcours d'interface

Navigation : Recettes, **Inspirations**, Planning, **Événements**, **Personnes**, Courses, **Stocks**, **Assistant**. Les trois actions « Ajouter une recette », « Organiser un repas », « Générer les courses » rejoignent le menu de création existant.

Assistant « Organiser un repas », pensé pour le téléphone :

1. Invités.
2. **Contraintes consolidées** — affichées avant tout choix de menu.
3. Menu et variantes — pastille de conformité par recette, motif lisible, adaptations proposées, aucune modification automatique.
4. Portions.
5. Courses — colonnes besoin / stock / achat, éléments à vérifier mis en évidence.

### 2.8 Intégration Infomaniak AI

- Infomaniak expose une route compatible OpenAI : `https://api.infomaniak.com/1/ai/{product_id}/openai/chat/completions` ([documentation](https://developer.infomaniak.com/docs/api/post/1/ai/{product_id}/openai/chat/completions)). Elle se configure donc comme un **fournisseur natif**, sans code. L'URL de base serait `https://api.infomaniak.com/1/ai/{product_id}/openai`.
- **À vérifier avec un compte réel avant la phase D** : URL de base exacte, modèles disponibles, prise en charge des sorties JSON structurées et des appels de fonctions. Si un modèle ne gère pas les appels de fonctions, repli sur les sorties structurées déjà utilisées par Mealie.
- `AssistantService` : boucle d'appels de fonctions au-dessus du client natif.
  - Outils de lecture : `search_recipes`, `get_recipe`, `get_available_ingredients`, `get_event_guests`, `check_dietary_constraints`, `calculate_portions`.
  - Outils de proposition : `propose_recipe_variant`, `draft_shopping_list`. Ils écrivent uniquement dans `pe_ai_proposals` (PENDING / ACCEPTED / REJECTED). L'application ne modifie les données qu'après acceptation par l'utilisateur.
- Toute quantité proposée est recalculée par le moteur déterministe. Tout résultat IA repasse par le moteur de conformité.
- **Minimisation.** Une seule frontière de sortie construit les messages. Elle n'envoie que des clés de contraintes et des effectifs (« 7 convives, sans gluten sur toute la préparation, 1 portion végétarienne »). Noms, notes et nature médicale ne sortent jamais. `get_event_guests` renvoie « convive 1…n ».
- **Indisponibilité.** Délai court, erreurs converties en état « assistant indisponible ». Aucun parcours des phases C et E ne dépend de l'IA.

### 2.9 Déploiement sur le NAS UGREEN

- Un script d'audit **en lecture seule** s'exécute d'abord sur le NAS : conteneurs, ports en écoute, projets Compose, réseaux, volumes. Le port est choisi d'après son résultat.
- Projet Compose isolé (`mealie-pe`), réseau dédié, volumes nommés dédiés. PostgreSQL sans port publié. Port de Mealie paramétré par `.env`, lié à l'interface Tailscale ou au reverse proxy seulement.
- Secrets par Docker secrets (`/run/secrets`, déjà lu par Mealie). Aucun secret dans le dépôt.
- Sauvegardes : `pg_dump` planifié + archive du volume de données, chiffrées, avec rétention et test de restauration.
- Retour arrière : images étiquetées `<version amont>-pe.<n>`, `pg_dump` automatique avant migration, `downgrade` de la branche `personal` testé. Le schéma cœur n'est jamais rétrogradé : on restaure la sauvegarde.
- Aucun déploiement avant que tous les tests de la phase soient verts.

---

## 3. Plan de tests

| Exigence (§11) | Test |
|---|---|
| Recalcul des portions, variantes, préférences individuelles | `tests/unit_tests/personal_tests/test_portions.py` |
| Addition des ingrédients, conversions | `test_requirements_aggregation.py` |
| Portée repas entier / préparation entière | `test_scope_resolution.py` |
| Compatibilité inconnue, pas de `VERIFIED` automatique | `test_compliance.py`, `test_verification_invariants.py` |
| Listes de courses, réconciliation | `tests/integration_tests/personal_tests/test_event_shopping.py` |
| Déduction des stocks | `test_pantry_deduction.py` (phase E) |
| Protection des données des invités | `test_ai_payload_minimisation.py` : inspection du message sortant ; `test_person_scoping.py` : cloisonnement groupe/foyer |
| Indisponibilité de l'IA | `test_assistant_unavailable.py` |
| Compatibilité native | Suite amont complète inchangée + `test_native_shopping_untouched.py` |
| Migrations | Montée et descente de la branche `personal` sur SQLite et PostgreSQL |
| **Scénario burgers** (7 convives, cœliaque, végétarien) | `test_event_burger_scenario.py`, bout en bout |

Interface : tests Vitest pour les composables, un parcours Playwright pour l'assistant d'événement en format téléphone.

---

## 4. Étapes de réalisation

Chaque étape est livrée avec ses tests, `mise run py:check` et `mise run ui:check` verts.

**Phase C — MVP**

| Étape | Contenu |
|---|---|
| C1 | Fondations du fork : branche Alembic `personal`, squelette des modules, chaînes séparées, `FORK.md` |
| C2 | Personnes, restrictions, consentement (API + écrans) |
| C3 | Statut de vérification des aliments, règles gluten, moteur de conformité |
| C4 | Événements, invités, menu, variantes, portions |
| C5 | Besoins, grand livre, projection et réconciliation des courses |
| C6 | Assistant « Organiser un repas » mobile, scénario burgers de bout en bout |
| C7 | Inspirations sans IA (saisie, statut, conversion manuelle en recette) |
| C8 | Compose NAS, sauvegardes, procédure de retour arrière |

**Phase D — IA** : D1 validation d'Infomaniak comme fournisseur natif ; D2 boucle d'outils et propositions ; D3 menus, adaptations, substitutions, recherche en langage naturel ; D4 structuration des inspirations.

**Phase E — Stocks** : E1 stock quantifié et déduction ; E2 conditionnements et arrondi d'achat ; E3 restes et suggestions anti-gaspillage.

---

## 5. Décisions à valider

1. **Variante = recette distincte** pour le MVP (recommandé), substitutions par ligne plus tard.
2. **Migrations sur une branche Alembic séparée**, au prix d'une ligne modifiée dans `init_db.py` (recommandé).
3. **Suivi des tags amont** plutôt que de `mealie-next` (recommandé).
4. **Construction de l'image** : GitHub Actions vers un registre privé (recommandé, le NAS ne compile pas le frontend) ou construction sur le NAS.
5. **Langue de l'interface du fork** : français seul, ou français + anglais.
6. **Facteurs d'appétit** : 0,75 / 1 / 1,25 proposés.

---

## 6. État de réalisation

Les décisions du §5 ont été prises selon les recommandations : variante = recette distincte, suivi des
tags amont, image construite par GitHub Actions, interface en français et en anglais, facteurs
d'appétit 0,75 / 1 / 1,25.

### Ce qui a changé par rapport au plan

| Sujet | Plan | Réalisation | Raison |
|---|---|---|---|
| Migrations | Branche Alembic `personal` dans l'historique de Mealie | Environnement de migration séparé (`mealie/alembic_personal`) avec sa propre table de version | La branche cassait la restauration de sauvegarde native et empêchait le retour à Mealie d'origine |
| Fichiers amont modifiés | 7 | 5 (liste dans `FORK.md`) | `alembic.ini`, `_all_models.py` et `nuxt.config.ts` n'ont pas eu besoin d'être touchés ; la sauvegarde native a demandé deux points d'accroche |
| Grand livre des courses | Lié à l'événement | Lié à un « plan de courses », dont la source est un événement, une plage du planning ou une sélection de recettes | Un seul mécanisme pour les trois sources demandées |
| Colonnes JSON | Type JSON | Texte JSON | La sauvegarde native ne sait pas restaurer des valeurs imbriquées |
| Clés étrangères vers `users` | Présentes | Supprimées | Elles auraient bloqué la suppression d'un utilisateur |
| Données produits | Non prévu | Recherche des produits Coop, Migros, Aldi et Lidl par Open Food Facts | Demande ajoutée ; voir la limite ci-dessous |
| Prix et budget | Non prévu | Table `pe_food_prices` (un prix par aliment et par magasin), budget d'un plan de courses par magasin, coût d'une recette par portion | Demande ajoutée. Les prix se saisissent à la main ; un service facultatif peut les relever (voir la limite ci-dessous) |
| Fil d'idées | Non prévu | Page « Idées » : recettes et inspirations classées et filtrées par étiquettes (stock, temps, saison, budget, restrictions, historique) | Demande ajoutée. Tout est calculé par l'application ; l'IA ne sert qu'à proposer de nouvelles idées, sur demande |

### Prix, budget et fil d'idées

- **Prix.** `pe_food_prices` garde, par foyer, le prix d'un aliment dans un magasin : prix du paquet,
  contenu, prix normal et fin de promotion. Le moteur (`engine/pricing.py`) arrondit au paquet entier,
  sauf pour un aliment vendu au poids, et ne mélange jamais des pièces avec un poids ou un volume. Une
  promotion terminée redonne le prix normal.
- **Budget.** `GET /api/households/shopping-plans/{id}/budget` reprend les lignes « à acheter » du plan
  et donne un total par magasin, plus un total « au meilleur prix de chaque article ». Chaque total
  dit combien d'articles il ne couvre pas : un total partiel n'est jamais présenté comme complet.
- **Fil d'idées.** `GET /api/households/ideas` renvoie des cartes avec leurs étiquettes. Les recettes
  qui enfreignent une restriction de l'utilisateur sont masquées par défaut, et le fil dit combien.
  « Compatible vérifié » n'apparaît que si chaque aliment a été vérifié à la main ; « Semble
  végétarien » est un indice tiré du nom des ingrédients et le dit. L'ordre change chaque jour.
- **Nouvelles idées par l'IA.** `POST /api/households/ideas/generate` envoie au fournisseur le mois,
  les produits de saison, le nom des aliments en stock (désactivable) et l'envie tapée, sans le nom
  des personnes. Les contraintes alimentaires ne partent que si l'utilisateur le coche, sous forme de
  consignes de cuisine (« sans gluten »), jamais avec un nom ou un motif. Chaque idée devient une
  inspiration, jamais une recette, et repasse par les vérifications de l'application.

### Interface

Une seconde passe a donné à l'application une apparence « verre liquide » et une organisation plus
directe : page d'accueil « Aujourd'hui », barre d'onglets flottante sur téléphone avec un bouton « + »
pour les actions courantes, en-têtes de page communs. Le détail est dans `FORK.md`, section « Apparence ».

### Limites connues

- **Produits des enseignes.** Les données viennent d'Open Food Facts, une base ouverte alimentée par
  ses contributeurs. Coop, Migros, Aldi et Lidl ne proposent pas d'API publique, et l'application ne
  contourne pas les protections de leurs sites. Conséquences : la couverture est partielle et cette
  base ne donne pas de prix.
- **Prix relevés en magasin.** L'application ne lit elle-même aucun site d'enseigne. Le relevé
  automatique passe par un service séparé et facultatif (`deploy/nas/price-bridge`), éteint par
  défaut, qui installe un programme tiers (`@nicktcode/swissgroceries-mcp`, licence PolyForm Shield,
  usage personnel). Ce programme n'est ni écrit ni vérifié par ce projet, et n'a pas été exécuté
  pendant le développement : le pont est testé contre un service simulé. Une enseigne peut cesser
  de répondre sans prévenir. Sans ce service, les prix saisis à la main suffisent au budget.
- **Saisons.** Le calendrier (`services/personal/data/seasonal_foods.json`) couvre 46 produits
  courants en Suisse, reconnus par leur nom en français, allemand, italien et anglais. C'est un
  repère, pas une garantie de provenance.
- **Infomaniak.** L'intégration n'a pas été essayée avec un compte réel. Elle est testée contre un
  fournisseur simulé (voir `docs/personal-edition/infomaniak.md`).
- **Substitutions par ligne d'ingrédient.** Une variante est une recette distincte. L'assistant peut
  proposer une variante avec substitutions ; l'application la crée comme nouvelle recette après
  acceptation.
- **SQLite.** Le fork vise PostgreSQL. SQLite n'applique pas les clés étrangères : il convient au
  développement, pas à la production.
- **Déploiement.** La pile Compose est validée syntaxiquement et ses scripts de sauvegarde et de
  restauration sont testés contre PostgreSQL, mais rien n'a été déployé sur le NAS.
