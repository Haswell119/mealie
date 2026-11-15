from enum import StrEnum


class RestrictionScope(StrEnum):
    """How far a dietary restriction reaches, from the narrowest to the widest."""

    INDIVIDUAL = "INDIVIDUAL"
    ENTIRE_MEAL = "ENTIRE_MEAL"
    ENTIRE_PREPARATION = "ENTIRE_PREPARATION"

    @property
    def rank(self) -> int:
        return list(RestrictionScope).index(self)


class RestrictionSeverity(StrEnum):
    PREFERENCE = "PREFERENCE"
    MODERATE = "MODERATE"
    STRICT = "STRICT"

    @property
    def rank(self) -> int:
        return list(RestrictionSeverity).index(self)


class RestrictionKind(StrEnum):
    MEDICAL = "MEDICAL"
    ALLERGY = "ALLERGY"
    INTOLERANCE = "INTOLERANCE"
    ETHICAL = "ETHICAL"
    PREFERENCE = "PREFERENCE"


class VerificationStatus(StrEnum):
    """The state of a food, a recipe or a menu for one restriction, from the best to the worst."""

    VERIFIED = "VERIFIED"
    UNVERIFIED = "UNVERIFIED"
    INCOMPATIBLE = "INCOMPATIBLE"

    @property
    def rank(self) -> int:
        return list(VerificationStatus).index(self)


class VerificationSource(StrEnum):
    MANUAL = "MANUAL"
    RULE = "RULE"
    AI_SUGGESTION = "AI_SUGGESTION"
    PRODUCT_LABEL = "PRODUCT_LABEL"


class FindingCode(StrEnum):
    """Why an ingredient or a tool is not verified for a restriction."""

    RULE_MATCH = "RULE_MATCH"
    LABEL_CHECK = "LABEL_CHECK"
    FREE_CLAIM = "FREE_CLAIM"
    NO_DATA = "NO_DATA"
    FREE_TEXT = "FREE_TEXT"
    STORED = "STORED"
    TOOL_CHECK = "TOOL_CHECK"
    NO_INGREDIENTS = "NO_INGREDIENTS"
    NO_VARIANT = "NO_VARIANT"
    MANUAL_ASSIGNMENT = "MANUAL_ASSIGNMENT"
    MISSING_SERVINGS = "MISSING_SERVINGS"
    RECIPE_NOT_FOUND = "RECIPE_NOT_FOUND"


class Appetite(StrEnum):
    SMALL = "SMALL"
    NORMAL = "NORMAL"
    LARGE = "LARGE"


class FoodPreferenceKind(StrEnum):
    LIKE = "LIKE"
    DISLIKE = "DISLIKE"


class MealEventStatus(StrEnum):
    DRAFT = "DRAFT"
    PLANNED = "PLANNED"
    DONE = "DONE"


class MealCourse(StrEnum):
    APERITIF = "APERITIF"
    STARTER = "STARTER"
    MAIN = "MAIN"
    SIDE = "SIDE"
    DESSERT = "DESSERT"
    OTHER = "OTHER"


class ShoppingPlanSource(StrEnum):
    EVENT = "EVENT"
    MEALPLAN = "MEALPLAN"
    RECIPES = "RECIPES"


class ShoppingPlanStatus(StrEnum):
    OPEN = "OPEN"
    DONE = "DONE"


class ShoppingPlanLineState(StrEnum):
    ACTIVE = "ACTIVE"
    DISMISSED = "DISMISSED"
    OBSOLETE = "OBSOLETE"


class InspirationKind(StrEnum):
    LINK = "LINK"
    PHOTO = "PHOTO"
    NOTE = "NOTE"
    VIDEO = "VIDEO"
    IDEA = "IDEA"


class InspirationStatus(StrEnum):
    INSPIRATION = "INSPIRATION"
    DRAFT = "DRAFT"
    VALIDATED = "VALIDATED"


class AiProposalKind(StrEnum):
    RECIPE_VARIANT = "RECIPE_VARIANT"
    SHOPPING_LIST = "SHOPPING_LIST"
    MENU = "MENU"
    SUBSTITUTION = "SUBSTITUTION"
    RECIPE_DRAFT = "RECIPE_DRAFT"


class AiProposalStatus(StrEnum):
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
