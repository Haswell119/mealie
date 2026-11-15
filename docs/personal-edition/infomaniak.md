# Assistant IA avec Infomaniak AI Tools

L'assistant est facultatif. Sans fournisseur IA, toute l'application fonctionne : personnes,
événements, plans de courses, stocks et inspirations ne dépendent jamais de l'IA.

## Ce que fait l'assistant

- Il répond en s'appuyant sur des **fonctions contrôlées** de l'application : recherche de recettes,
  lecture d'une recette, stock disponible, contraintes d'un événement, vérification d'une recette,
  calcul des portions.
- Il peut **proposer** une variante de recette, un menu ou une liste de courses. Une proposition ne
  change rien tant que vous ne l'acceptez pas dans la page « Assistant IA ».
- Les quantités viennent toujours du moteur de calcul de l'application, jamais du modèle.

## Ce qui sort de l'application

| Envoyé au fournisseur | Jamais envoyé |
|---|---|
| Votre message, après remplacement des noms connus par « convive 1 », « convive 2 »… | Le nom des personnes |
| Les contraintes sans nom : « sans gluten sur toute la préparation », « 1 convive sans viande » | Les remarques sur une personne, la note de consentement |
| Le nom et les ingrédients des recettes consultées | La nature médicale d'une restriction |
| Le stock confirmé (aliment, quantité) | Votre adresse, votre identifiant, vos mots de passe |

Le test `tests/integration_tests/personal_tests/test_assistant.py` inspecte chaque requête sortante et
échoue si un nom ou une remarque y figure.

## Configuration

Infomaniak AI Tools expose une API compatible OpenAI. Mealie sait déjà parler à ce type d'API : il
n'y a aucun code à ajouter, seulement un fournisseur à déclarer.

1. Dans le Manager Infomaniak, ouvrir **AI Tools**, noter l'**identifiant du produit** et créer un
   **jeton d'API** avec la portée *AI Tools*.
2. Dans Mealie : **Paramètres du groupe → Fournisseurs IA → Ajouter**.
3. Remplir :

| Champ | Valeur |
|---|---|
| Nom | `Infomaniak` |
| URL de base | `https://api.infomaniak.com/1/ai/<identifiant du produit>/openai` |
| Clé d'API | le jeton créé à l'étape 1 |
| Modèle | un modèle de la liste du Manager Infomaniak |
| Délai | `120` |

4. Cliquer sur **Tester**. Mealie envoie un vrai message et affiche le résultat.
5. Choisir ce fournisseur comme **fournisseur par défaut**.

### Points à valider avec votre compte

Je n'ai pas pu tester contre un compte Infomaniak réel. La route documentée est
`https://api.infomaniak.com/1/ai/{product_id}/openai/chat/completions`
([documentation](https://developer.infomaniak.com/docs/api/post/1/ai/{product_id}/openai/chat/completions)) ;
l'URL de base ci-dessus en est déduite. Le bouton **Tester** dit immédiatement si elle est correcte.

- **Appels de fonctions.** Tous les modèles ne les prennent pas en charge. Si le modèle les refuse,
  l'assistant continue en conversation simple : il répond, mais ne peut plus consulter vos recettes
  ni créer de proposition. Choisir alors un autre modèle.
- **Images et audio.** L'import de recette depuis une photo ou une vidéo (fonctions natives de
  Mealie) demande un modèle qui lit les images et un modèle de transcription. Les déclarer comme
  fournisseurs séparés si Infomaniak les propose.

## La clé d'API

Mealie enregistre la clé dans la base de données, en clair. Elle figure donc dans les sauvegardes :
c'est une des raisons pour lesquelles `deploy/nas` chiffre toutes les sauvegardes.
