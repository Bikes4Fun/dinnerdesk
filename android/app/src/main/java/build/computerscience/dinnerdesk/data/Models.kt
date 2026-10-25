package build.computerscience.dinnerdesk.data

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.booleanOrNull
import kotlinx.serialization.json.intOrNull
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive

// The server's JSON shapes. Mirrors ios/dinnerdesk/Models.swift and KitchenAPI.swift.

@Serializable
data class Plan(
    val id: Int,
    val title: String = "This week",
    @SerialName("start_date") val startDate: String = "",
    val days: Int = 7,
    val slots: List<PlanSlot> = emptyList(),
    val status: String? = null,
    @SerialName("suggested_recipe_ids") val suggestedRecipeIds: List<Int>? = null,
    @SerialName("suggestion_note") val suggestionNote: String? = null,
    @SerialName("suggestion_reasons") val suggestionReasons: Map<String, List<String>>? = null,
)

@Serializable
data class PlanSlot(
    val id: Int,
    @SerialName("recipe_id") val recipeId: Int,
    @SerialName("recipe_name") val recipeName: String = "",
    @SerialName("photo_path") val photoPath: String? = null,
    @SerialName("cooking_minutes") val cookingMinutes: Int? = null,
    @SerialName("day_index") val dayIndex: Int? = null,
    @SerialName("meal_type") val mealType: String = "dinner",
    val servings: Int = 4,
    val cooked: Boolean = false,
    /** Household thumbs on this meal: 1 up, -1 down, null/0 none. */
    val rating: Int? = null,
) {
    val asBody: Map<String, Any?>
        get() = buildMap {
            put("id", id)
            put("recipe_id", recipeId)
            put("meal_type", mealType)
            put("servings", servings)
            if (dayIndex != null) put("day_index", dayIndex)
        }
}

@Serializable
data class RecipeList(
    val recipes: List<RecipeSummary> = emptyList(),
    /** Every recipe this kitchen can search, before filters. */
    val total: Int? = null,
)

@Serializable
data class RecipeSummary(
    val id: Int,
    val name: String,
    val servings: Int? = null,
    @SerialName("cooking_minutes") val cookingMinutes: Int? = null,
    @SerialName("photo_path") val photoPath: String? = null,
    val favorited: Boolean = false,
    @SerialName("to_try") val toTry: Boolean = false,
    val catalog: Boolean = false,
    val hidden: Boolean = false,
    val tags: List<String> = emptyList(),
    val ingredients: List<String> = emptyList(),
) {
    val isExtra: Boolean
        get() {
            if ("main_dish" in tags || "full_meal" in tags) return false
            return tags.any { it == "sauce" || it == "dressing" || it == "component" }
        }
    val isMeal: Boolean get() = !isExtra
}

@Serializable
data class RecipeDetail(
    val id: Int,
    val name: String,
    val servings: Int? = null,
    @SerialName("cooking_minutes") val cookingMinutes: Int? = null,
    @SerialName("photo_path") val photoPath: String? = null,
    /** The photo was made with AI; the recipe page says so (#33). */
    @SerialName("photo_ai") val photoAI: Boolean = false,
    /** The photo was taken for a similar recipe (#33). */
    @SerialName("photo_shared") val photoShared: Boolean = false,
    val favorited: Boolean = false,
    @SerialName("to_try") val toTry: Boolean = false,
    val hidden: Boolean = false,
    val catalog: Boolean = false,
    val tags: List<String> = emptyList(),
    val ingredients: List<IngredientLine> = emptyList(),
    val instructions: List<InstructionStep> = emptyList(),
    @SerialName("instructions_source") val instructionsSource: String? = null,
    @SerialName("instructions_copied_from_third_party") val instructionsCopiedFromThirdParty: Boolean? = null,
    /** Where a kitchen's own recipe came from, when it has a web link. */
    @SerialName("source_url") val sourceUrl: String? = null,
) {
    val sourceLink: String?
        get() {
            if (catalog) return null
            val raw = sourceUrl ?: return null
            val scheme = raw.substringBefore(':', "").lowercase()
            return if (scheme == "http" || scheme == "https") raw else null
        }
    val instructionsCustomized: Boolean
        get() = instructionsSource == "dinnerdesk" && instructionsCopiedFromThirdParty == false
    val prettyTags: String get() = tags.joinToString(" · ") { it.replace("_", " ") }
}

@Serializable
data class IngredientLine(
    val name: String,
    val quantity: String? = null,
    @SerialName("ingredient_id") val ingredientId: Int? = null,
)

@Serializable
data class InstructionStep(
    val text: String? = null,
    val step: String? = null,
    val prep: Boolean? = null,
    val ings: String? = null,
) {
    val displayText: String get() = text ?: step ?: ""

    fun asBody(): Map<String, Any?> = buildMap {
        put("text", displayText)
        put("prep", prep ?: false)
        if (!ings.isNullOrEmpty()) put("ings", ings)
    }
}

@Serializable
data class GroceryList(val lines: List<GroceryLine> = emptyList())

@Serializable
data class UsedMeal(
    @SerialName("id") val recipeId: Int? = null,
    val name: String,
    @SerialName("photo_path") val photoPath: String? = null,
    @SerialName("cooking_minutes") val cookingMinutes: Int? = null,
    val quantity: String = "",
)

@Serializable
data class GroceryLine(
    val id: Int,
    val name: String,
    val quantity: String = "",
    val aisle: String = "other",
    val store: String = "",
    val checked: Boolean = false,
    @SerialName("never_shop") val neverShop: Boolean = false,
    @SerialName("from_pantry") val fromPantry: Boolean = false,
    @SerialName("used_by") val usedBy: List<String> = emptyList(),
    @SerialName("used_in") val usedIn: List<UsedMeal> = emptyList(),
    @SerialName("ingredient_photo_path") val ingredientPhotoPath: String? = null,
)

@Serializable
data class GroceryItemHits(val items: List<Item> = emptyList()) {
    @Serializable
    data class Item(val name: String)
}

@Serializable
data class PrepList(val tasks: List<PrepTask> = emptyList())

@Serializable
data class PrepTask(
    val id: Int,
    val title: String = "",
    val notes: String = "",
    val done: Boolean = false,
    val meals: List<PrepMeal> = emptyList(),
    val quantities: List<String> = emptyList(),
    /** True when the app picked these steps (no step in the recipe was tagged Prep). */
    val auto: Boolean? = null,
    /** Weekend prep section (#21): veg, herbs, protein, cheese, sauce or other. */
    val section: String? = null,
    val item: String? = null,
    val action: String? = null,
    /** 👍/👎 on the whole item (1, -1, 0) and why a 👎 (a PrepReason id, or ""). */
    val rating: Int? = null,
    val reason: String? = null,
    @SerialName("reason_note") val reasonNote: String? = null,
) {
    /** What the row says: "Peel and mince garlic". */
    val name: String get() = title
}

/** Why a cook reports a recipe. Ids match app/models.py RECIPE_REPORT_REASONS. */
enum class RecipeReportReason(val id: String, val label: String) {
    Ingredients("ingredients", "Ingredients are wrong or missing"),
    Steps("steps", "Steps are wrong or confusing"),
    Diet("diet", "Shows up despite my diet or allergies"),
    Photo("photo", "Photo doesn't match"),
    Duplicate("duplicate", "Duplicate of another recipe"),
    TurnedOut("turned_out", "Didn't turn out well"),
    Other("other", "Something else"),
}

/** Why a prep item isn't worth doing ahead. Ids match app/models.py PREP_REASONS. */
enum class PrepReason(val id: String, val label: String) {
    DayOf("day_of", "Better done day-of"),
    KeptBadly("kept_badly", "Didn't keep well"),
    TooSmall("too_small", "Too small to bother"),
    PrepDifferently("prep_differently", "Prep it differently"),
    NotPrep("not_prep", "Not a prep step");

    companion object {
        fun of(id: String?) = entries.firstOrNull { it.id == id }
    }
}

@Serializable
data class PrepMeal(
    val id: Int,
    val name: String = "",
    /** The meal's cook day on the plan ("Mon"), or null when it isn't scheduled. */
    val day: String? = null,
    val instructions: List<String> = emptyList(),
    val steps: List<PrepStep>? = null,
)

@Serializable
data class PrepStep(
    val key: String,
    val text: String = "",
    val auto: Boolean? = null,
    val rating: Int? = null,
    val done: Boolean? = null,
    /** The household added this step with "Missing a prep step?". */
    val added: Boolean? = null,
)

@Serializable
data class MissingPrepList(val meals: List<MissingPrepMeal> = emptyList())

@Serializable
data class MissingPrepMeal(
    val id: Int,
    val name: String = "",
    val day: String? = null,
    val steps: List<MissingPrepStep> = emptyList(),
)

@Serializable
data class MissingPrepStep(
    val key: String,
    val text: String = "",
    /** The recipe step it comes from (1-based). */
    val step: Int = 0,
    val added: Boolean = false,
    val note: String = "",
)

@Serializable
data class PrepItemResult(val done: Boolean)

@Serializable
data class MealRating(@SerialName("recipe_id") val recipeId: Int = 0, val rating: Int = 0)

@Serializable
data class ShopStore(val id: String, val name: String) {
    companion object {
        val defaults = listOf(
            ShopStore("costco", "Costco"),
            ShopStore("walmart", "Walmart"),
            ShopStore("local", "Local grocer"),
            ShopStore("farmers", "Farmers market"),
        )
    }
}

@Serializable
data class ShopAisle(val id: String, val name: String, val number: String = "") {
    companion object {
        val defaults = listOf(
            ShopAisle("produce", "Produce"),
            ShopAisle("dairy", "Dairy, Cheese & Eggs"),
            ShopAisle("meat", "Meat & Seafood"),
            ShopAisle("pantry", "Pantry"),
            ShopAisle("other", "Other"),
        )
    }
}

/** Household prefs are free-form JSON, so read them leniently. */
@Serializable
data class Household(val name: String? = null, val prefs: JsonObject? = null) {
    private val grocery: JsonObject? get() = prefs?.get("grocery") as? JsonObject

    val stores: List<ShopStore>?
        get() = (grocery?.get("stores"))?.let { element ->
            try { element.jsonArray.mapNotNull { Api.json.decodeFromJsonElement(ShopStore.serializer(), it) } } catch (_: Exception) { null }
        }
    val aisles: List<ShopAisle>?
        get() = (grocery?.get("aisles"))?.let { element ->
            try {
                element.jsonArray.mapNotNull {
                    val o = it.jsonObject
                    ShopAisle(o.string("id") ?: return@mapNotNull null, o.string("name") ?: return@mapNotNull null, o.string("number") ?: "")
                }
            } catch (_: Exception) { null }
        }

    fun groceryFlag(key: String): Boolean? = (grocery?.get(key) as? JsonPrimitive)?.booleanOrNull

    /** Default servings for new plan meals. A bad value is ignored rather than failing the household. */
    val familyPortions: Int?
        get() = (prefs?.get("family_portions") as? JsonPrimitive)?.intOrNull?.takeIf { it in 1..50 }
}

fun JsonObject.string(key: String): String? = (this[key] as? JsonPrimitive)?.takeIf { it.isString }?.content
fun JsonObject.bool(key: String): Boolean? = (this[key] as? JsonPrimitive)?.booleanOrNull
fun JsonObject.int(key: String): Int? = (this[key] as? JsonPrimitive)?.intOrNull
fun JsonObject.strings(key: String): List<String>? = try {
    this[key]?.jsonArray?.mapNotNull { it.jsonPrimitive.takeIf { p -> p.isString }?.content }
} catch (_: Exception) { null }
fun JsonObject.obj(key: String): JsonObject? = this[key] as? JsonObject

/** Only the saved-plan listing has a status discriminator. */
@Serializable
data class SavedPlan(
    val id: Int,
    val title: String = "",
    @SerialName("start_date") val startDate: String = "",
    val days: Int = 7,
    val slots: List<PlanSlot> = emptyList(),
    val status: String = "",
    val decision: String? = null,
    /** When the plan was saved (ISO 8601). Older servers don't send it. */
    @SerialName("created_at") val createdAt: String? = null,
)

@Serializable
data class PendingSuggestion(val plan: Plan? = null)

@Serializable
data class RecipeSuggestions(@SerialName("recipe_ids") val recipeIds: List<Int> = emptyList())

@Serializable
data class PlanList(val plans: List<SavedPlan> = emptyList())

@Serializable
data class SuggestionCapabilities(
    val version: Int = 0,
    val review: Boolean = false,
    val resize: Boolean = false,
    val swap: Boolean = false,
)

@Serializable
data class SwapOption(
    val id: Int,
    val name: String,
    @SerialName("cooking_minutes") val cookingMinutes: Int? = null,
    @SerialName("photo_path") val photoPath: String? = null,
)

@Serializable
data class SwapOptions(val recipes: List<SwapOption> = emptyList())

@Serializable
data class Ok(val ok: Boolean = true)

@Serializable
data class AuthStatus(
    val required: Boolean = false,
    @SerialName("household_id") val householdId: Int? = null,
    val authenticated: Boolean = false,
    val email: String? = null,
    @SerialName("has_email") val hasEmail: Boolean? = null,
    val admin: Boolean? = null,
)

@Serializable
data class HouseholdMember(
    val id: Int,
    val email: String = "",
    @SerialName("joined_at") val joinedAt: String? = null,
    @SerialName("household_role") val householdRole: String? = null,
)

@Serializable
data class HouseholdMembers(val members: List<HouseholdMember> = emptyList())

@Serializable
data class HouseholdInvite(val token: String)

@Serializable
data class KitchenPantryItem(
    val id: Int? = null,
    val name: String,
    val have: Boolean = false,
    @SerialName("never_shop") val neverShop: Boolean = false,
    val quantity: String = "",
    val store: String? = null,
    val aisle: String? = null,
)

@Serializable
data class KitchenPantryList(val items: List<KitchenPantryItem> = emptyList())

@Serializable
data class KitchenItemSearch(val items: List<GroceryItemHits.Item> = emptyList(), val custom: String? = null)

@Serializable
data class KitchenOverride(
    val id: Int,
    @SerialName("from_name") val fromName: String,
    @SerialName("to_name") val toName: String,
)

@Serializable
data class KitchenOverrideList(val items: List<KitchenOverride> = emptyList())

@Serializable
data class ItemPlace(val name: String, val store: String? = null, val aisle: String? = null)

@Serializable
data class ItemPlaceList(val items: List<ItemPlace> = emptyList())

/** One grocery item and where it's bought. */
data class ItemPlacement(val name: String, val store: String, val aisle: String) {
    val id: String get() = name.lowercase()
}

@Serializable
data class RecipeDraft(
    val name: String = "",
    val servings: Int? = null,
    @SerialName("cooking_minutes") val cookingMinutes: Int? = null,
    @SerialName("source_url") val sourceUrl: String? = null,
    @SerialName("image_url") val imageUrl: String? = null,
    @SerialName("ingredient_lines") val ingredientLines: List<String> = emptyList(),
    val instructions: List<InstructionStep> = emptyList(),
)

@Serializable
data class CreatedRecipe(val id: Int)
