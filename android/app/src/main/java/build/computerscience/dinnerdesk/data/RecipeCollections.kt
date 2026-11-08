package build.computerscience.dinnerdesk.data

/** Search filter chips on the Recipes screen. Same keys and labels as web and iOS. */
enum class RecipeSearchFilter(val label: String) {
    Fav("Your favorites"), TryLater("To try"), Popular("Popular"), Quick("Quick"), Pantry("Uses pantry"),
    Hidden("Hidden"), ComingSoon("Coming soon"),
}

/**
 * The recipe lists every Recipes screen shows, built one way. Web (recipeCollections.js) and iOS
 * (RecipeCollections in Models.swift) have the same class with the same members and rules.
 * Coming-soon recipes (our photo, steps not written yet) stay out of every themed list; they have
 * their own list and come last in [all].
 */
class RecipeCollections(recipes: List<RecipeSummary>) {
    private val byName = compareBy(String.CASE_INSENSITIVE_ORDER) { r: RecipeSummary -> r.name }

    val ready: List<RecipeSummary> = recipes.filter { !it.comingSoon }
    val comingSoon: List<RecipeSummary> = recipes.filter { it.comingSoon }.sortedWith(byName)
    val favorites: List<RecipeSummary> = ready.filter { it.favorited }
    val toTry: List<RecipeSummary> = ready.filter { it.toTry }
    val mine: List<RecipeSummary> = ready.filter { !it.catalog }
    val meals: List<RecipeSummary> = ready.filter { !it.isExtra }
    val sauces: List<RecipeSummary> = ready.filter { it.isExtra }
    val popular: List<RecipeSummary> = meals.filter { "popular" in it.tags }
    val simple: List<RecipeSummary> = meals.filter { (it.cookingMinutes ?: 99) <= 20 }
    /** Every meal A–Z, then the coming-soon ones. */
    val all: List<RecipeSummary> = meals.sortedWith(byName) + comingSoon

    /** [rows] narrowed by the search filters that are on. Hidden picks the source list, so the screen handles it. */
    fun filter(rows: List<RecipeSummary>, filters: Set<RecipeSearchFilter>, pantryHave: Set<String>): List<RecipeSummary> {
        var out = if (RecipeSearchFilter.ComingSoon in filters) rows.filter { it.comingSoon } else rows
        if (RecipeSearchFilter.Fav in filters) out = out.filter { it.favorited }
        if (RecipeSearchFilter.TryLater in filters) out = out.filter { it.toTry }
        if (RecipeSearchFilter.Popular in filters) out = out.filter { "popular" in it.tags }
        if (RecipeSearchFilter.Quick in filters) out = out.filter { (it.cookingMinutes ?: 99) <= 30 }
        if (RecipeSearchFilter.Pantry in filters) out = out.filter { PantryMatch.uses(it.ingredients, pantryHave) }
        return out
    }
}
