package build.computerscience.dinnerdesk.data

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import coil.imageLoader
import coil.request.ImageRequest
import android.content.Context
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.async
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import java.time.LocalDate

/** The household's plan, recipes, grocery list and prep. Mirrors ios/dinnerdesk/Store.swift. */
class Store(private val scope: CoroutineScope, private val context: Context) {
    var proposalError by mutableStateOf<String?>(null)
    var proposal by mutableStateOf<Plan?>(null)
    /** Loading a saved proposal must not interrupt launch or pull-to-refresh. */
    var showingProposal by mutableStateOf(false)
    var generatingProposal by mutableStateOf(false)
        private set

    private val planState = mutableStateOf<Plan?>(null)
    var plan: Plan?
        get() = planState.value
        set(value) {
            val old = planState.value
            planState.value = value
            if (value == null) return
            ResponseCache.save(value, "plans/current")
            // Prep follows the plan's meals, servings and cooked state.
            if (prepShape(old) != prepShape(value)) Freshness.invalidate(Freshness.PREP)
        }

    var recipes by mutableStateOf<List<RecipeSummary>>(emptyList())
    /** How many recipes search covers, shown in the search box placeholder. */
    var recipeTotal by mutableStateOf<Int?>(null)

    private val groceryState = mutableStateOf<List<GroceryLine>>(emptyList())
    /** Saved on every change, so a relaunch with no signal shows the list as the person left it. */
    var grocery: List<GroceryLine>
        get() = groceryState.value
        set(value) {
            groceryState.value = value
            val id = plan?.id ?: return
            ResponseCache.save(GroceryList(value), "plans/$id/grocery")
        }

    /** Household default servings, for recipes not yet on the plan. */
    var familyPortions by mutableStateOf<Int?>(null)
        private set
    /** Dinnerdesk admins can tag recipe steps as Prep. */
    var isAdmin by mutableStateOf(false)
        private set
    var stores by mutableStateOf(ShopStore.defaults)
    var aisles by mutableStateOf(ShopAisle.defaults)
    var groupByStore by mutableStateOf(false)
    var showMeals by mutableStateOf(false)
    var hideChecked by mutableStateOf(true)
    var showAisleNums by mutableStateOf(false)
    var showEmoji by mutableStateOf(false)
    var prepTasks by mutableStateOf<List<PrepTask>>(emptyList())
    var error by mutableStateOf<String?>(null)

    private var groceryPrefsLoaded = false
    private var paintedFromCache = false
    private var loadingAll = false
    /** Bumped when the account changes. A request started before then belongs to the previous kitchen. */
    private var generation = 0
    private var prefetchJob: Job? = null
    private var hiddenRecipes: List<RecipeSummary>? = null

    /** Runs store work the way a SwiftUI `Task {}` does: it outlives the screen that started it. */
    fun launch(block: suspend Store.() -> Unit): Job = scope.launch { block() }

    private fun prepShape(plan: Plan?): List<String> =
        (plan?.slots ?: emptyList()).map { "${it.id}:${it.recipeId}:${it.servings}:${it.cooked}" }

    private fun fail(error: Throwable) {
        if (Api.isCancellation(error)) return
        this.error = Api.message(error)
    }

    val weekIds: Set<Int> get() = plan?.slots?.map { it.recipeId }?.toSet() ?: emptySet()

    fun onWeek(recipeId: Int) = recipeId in weekIds

    /** Shows what's saved on the device right away, then refreshes from the server. */
    suspend fun loadAll(onlyIfStale: Boolean = false) {
        paintFromCache()
        if (onlyIfStale && loadingAll) return
        if (onlyIfStale && Freshness.isFresh(Freshness.PLAN) && Freshness.isFresh(Freshness.RECIPES)) {
            loadGrocery(onlyIfStale = true)
            return
        }
        val gen = generation
        loadingAll = true
        error = null
        try {
            coroutineScope {
                val planBox = async { Api.get<Plan>("plans/current", cache = true) }
                val recipeBox = async { Api.get<RecipeList>("recipes", mapOf("limit" to "400"), cache = true) }
                val loaded = planBox.await()
                if (gen != generation) return@coroutineScope
                plan = loaded
                Freshness.mark(Freshness.PLAN)
                val pending = try { Api.get<PendingSuggestion>("suggestions/current", reportErrors = false) } catch (e: CancellationException) { throw e } catch (_: Exception) { null }
                if (gen != generation) return@coroutineScope
                if (pending?.plan?.status == "suggested" && pending.plan.suggestedRecipeIds != null) proposal = pending.plan
                val recipeList = recipeBox.await()
                if (gen != generation) return@coroutineScope
                recipes = recipeList.recipes
                recipeTotal = recipeList.total ?: recipeTotal
                Freshness.mark(Freshness.RECIPES)
                reloadGrocery()
                loadGroceryPrefs(onlyIfStale)
                if (gen != generation) return@coroutineScope
                prefetchJob?.cancel()
                prefetchJob = scope.launch { prefetchRecipes() }
            }
        } catch (e: Throwable) {
            if (gen == generation) fail(e)
        } finally {
            if (gen == generation) loadingAll = false
        }
    }

    /** Signed in, out or as someone else: forget the previous kitchen and load this one. */
    suspend fun switchAccount(load: Boolean = true) {
        generation += 1
        prefetchJob?.cancel()
        prefetchJob = null
        loadingAll = false
        paintedFromCache = true
        error = null
        proposalError = null
        showingProposal = false
        stores = ShopStore.defaults
        aisles = ShopAisle.defaults
        groupByStore = false
        showMeals = false
        hideChecked = true
        showAisleNums = false
        showEmoji = false
        planState.value = null
        proposal = null
        recipes = emptyList()
        groceryState.value = emptyList()
        prepTasks = emptyList()
        hiddenRecipes = null
        familyPortions = null
        isAdmin = false
        groceryPrefsLoaded = false
        if (load) loadAll()
    }

    /** First paint from the device: the last plan, recipes, grocery list and prep. */
    private fun paintFromCache() {
        if (paintedFromCache) return
        paintedFromCache = true
        if (plan == null) Api.cached<Plan>("plans/current")?.let { plan = it }
        if (recipes.isEmpty()) Api.cached<RecipeList>("recipes", mapOf("limit" to "400"))?.let {
            recipes = it.recipes
            recipeTotal = it.total
        }
        plan?.let { p ->
            if (grocery.isEmpty()) Api.cached<GroceryList>("plans/${p.id}/grocery")?.let { groceryState.value = it.lines }
            if (prepTasks.isEmpty()) Api.cached<PrepList>("plans/${p.id}/prep")?.let { prepTasks = it.tasks }
        }
        Api.cached<Household>("household")?.let { applyHousehold(it) }
    }

    /** Full recipes and photos for planned meals, then favorites and To try, so cooking works offline. */
    private suspend fun prefetchRecipes() {
        val ids = mutableListOf<Int>()
        val photos = mutableListOf<String?>()
        for (slot in plan?.slots ?: emptyList()) if (slot.recipeId !in ids) { ids += slot.recipeId; photos += slot.photoPath }
        for (recipe in recipes) if ((recipe.favorited || recipe.toTry) && recipe.id !in ids) { ids += recipe.id; photos += recipe.photoPath }
        val week = 7 * 24 * 60 * 60.0
        val gen = generation
        for ((id, photo) in ids.zip(photos)) {
            if (!scope.isActive || gen != generation) return
            val age = ResponseCache.age(ResponseCache.key("recipes/$id"))
            if (age == null || age > week) {
                try { Api.get<RecipeDetail>("recipes/$id", reportErrors = false, cache = true) } catch (e: CancellationException) { throw e } catch (_: Exception) {}
            }
            Api.photoUrl(photo)?.let { context.imageLoader.execute(ImageRequest.Builder(context).data(it).build()) }
        }
    }

    /** Signed-in status for admin-only controls, fetched once per launch. */
    suspend fun loadAdmin() {
        if (Freshness.isFresh(Freshness.AUTH, Double.MAX_VALUE)) return
        val gen = generation
        val status = try { AuthApi.status() } catch (e: CancellationException) { throw e } catch (_: Exception) { return }
        if (gen != generation) return
        isAdmin = status.admin == true
        Freshness.mark(Freshness.AUTH)
    }

    suspend fun searchRecipes(q: String) {
        try {
            val query = mutableMapOf("limit" to "400")
            val trimmed = q.trim()
            if (trimmed.isNotEmpty()) query["q"] = trimmed
            recipes = Api.get<RecipeList>("recipes", query).recipes
        } catch (e: Throwable) {
            fail(e)
        }
    }

    /** `onlyIfStale` (opening Recipes) reuses the list from earlier in this launch. */
    suspend fun loadHiddenRecipes(onlyIfStale: Boolean = false): List<RecipeSummary> {
        val query = mapOf("limit" to "400", "hidden" to "true")
        if (hiddenRecipes == null) Api.cached<RecipeList>("recipes", query)?.let { hiddenRecipes = it.recipes }
        if (onlyIfStale && hiddenRecipes != null && Freshness.isFresh(Freshness.HIDDEN)) return hiddenRecipes!!
        val gen = generation
        return try {
            val box: RecipeList = Api.get("recipes", query, cache = true)
            if (gen != generation) return hiddenRecipes ?: emptyList()
            hiddenRecipes = box.recipes
            Freshness.mark(Freshness.HIDDEN)
            box.recipes
        } catch (e: Throwable) {
            fail(e)
            hiddenRecipes ?: emptyList()
        }
    }

    suspend fun toggleFavorite(recipe: RecipeSummary) {
        val on = !recipe.favorited
        recipes = recipes.map { if (it.id == recipe.id) it.copy(favorited = on) else it }
        try {
            Api.send<RecipeDetail>("recipes/${recipe.id}/favorite", "PUT", mapOf("on" to on), cacheAs = "recipes/${recipe.id}")
        } catch (e: Throwable) {
            if (Api.isCancellation(e)) return
            val message = Api.message(e)
            loadAll()
            error = message
        }
    }

    suspend fun setFavorite(id: Int, on: Boolean): RecipeDetail? {
        recipes = recipes.map { if (it.id == id) it.copy(favorited = on) else it }
        return try {
            Api.send("recipes/$id/favorite", "PUT", mapOf("on" to on), cacheAs = "recipes/$id")
        } catch (e: Throwable) {
            fail(e); null
        }
    }

    suspend fun toggleTryLater(recipe: RecipeSummary) {
        val on = !recipe.toTry
        recipes = recipes.map { if (it.id == recipe.id) it.copy(toTry = on) else it }
        setTryLater(recipe.id, on)
    }

    suspend fun setTryLater(id: Int, on: Boolean): RecipeDetail? {
        recipes = recipes.map { if (it.id == id) it.copy(toTry = on) else it }
        return try {
            Api.send("recipes/$id/try", "PUT", mapOf("on" to on), cacheAs = "recipes/$id")
        } catch (e: Throwable) {
            fail(e); null
        }
    }

    suspend fun setHidden(id: Int, on: Boolean): RecipeDetail? {
        Freshness.invalidate(Freshness.HIDDEN)
        if (on) recipes = recipes.filter { it.id != id }
        return try {
            val next: RecipeDetail = Api.send("recipes/$id/hidden", "PUT", mapOf("on" to on), cacheAs = "recipes/$id")
            if (!on) searchRecipes("")
            next
        } catch (e: Throwable) {
            if (Api.isCancellation(e)) return null
            val message = Api.message(e)
            loadAll()
            error = message
            null
        }
    }

    suspend fun toggleWeek(recipe: RecipeSummary) {
        if (onWeek(recipe.id)) removeFromWeek(recipe.id) else addToWeek(recipe.id, null)
    }

    suspend fun addToWeek(recipeId: Int, servings: Int?) {
        try {
            val current = currentPlan()
            val slots = current.slots.map { it.asBody }.toMutableList<Map<String, Any?>>()
            slots += buildMap {
                put("recipe_id", recipeId)
                put("meal_type", "dinner")
                if (servings != null) put("servings", servings)
            }
            plan = Api.send("plans/${current.id}/slots", "PUT", mapOf("slots" to slots))
            reloadGrocery()
        } catch (e: Throwable) {
            fail(e)
        }
    }

    suspend fun removeFromWeek(recipeId: Int) {
        try {
            val current = currentPlan()
            val slots = current.slots.filter { it.recipeId != recipeId }.map { it.asBody }
            plan = Api.send("plans/${current.id}/slots", "PUT", mapOf("slots" to slots))
            reloadGrocery()
        } catch (e: Throwable) {
            fail(e)
        }
    }

    suspend fun unschedule(slot: PlanSlot) = patchSlot(slot.id, mapOf("unschedule" to true))

    suspend fun toggleCooked(slot: PlanSlot) {
        applyLocalSlot(slot.id) { it.copy(cooked = !it.cooked) }
        patchSlot(slot.id, mapOf("cooked" to !slot.cooked), reloadOnError = true)
    }

    suspend fun setServings(slot: PlanSlot, servings: Int) {
        val next = servings.coerceIn(1, 50)
        if (next == slot.servings) return
        applyLocalSlot(slot.id) { it.copy(servings = next) }
        patchSlot(slot.id, mapOf("servings" to next), refreshGrocery = true)
    }

    suspend fun setServingsForRecipe(recipeId: Int, servings: Int) {
        val next = servings.coerceIn(1, 50)
        val slots = (plan?.slots ?: emptyList()).filter { it.recipeId == recipeId }
        if (slots.isEmpty()) return
        for (slot in slots) if (slot.servings != next) {
            applyLocalSlot(slot.id) { it.copy(servings = next) }
            patchSlot(slot.id, mapOf("servings" to next), refreshGrocery = false)
        }
        reloadGrocery()
    }

    suspend fun removeSlot(slot: PlanSlot) {
        try {
            plan = Api.send<Plan>("slots/${slot.id}", "DELETE")
            reloadGrocery()
        } catch (e: Throwable) {
            if (Api.isCancellation(e)) return
            val message = Api.message(e)
            loadAll()
            error = message
        }
    }

    suspend fun markAllCooked() {
        for (slot in (plan?.slots ?: emptyList()).filter { !it.cooked }) {
            applyLocalSlot(slot.id) { it.copy(cooked = true) }
            patchSlot(slot.id, mapOf("cooked" to true), reloadOnError = true)
        }
    }

    /** `onlyIfStale` (opening Grocery) uses the saved list while fresh; `rebuild` (pull-to-refresh) rebuilds it first. */
    suspend fun loadGrocery(onlyIfStale: Boolean = false, rebuild: Boolean = false) {
        if (onlyIfStale && Freshness.isFresh(Freshness.GROCERY)) {
            loadGroceryPrefs(onlyIfStale = true)
            return
        }
        val gen = generation
        try {
            val current = currentPlan()
            val list: GroceryList = if (rebuild) {
                Api.send("plans/${current.id}/grocery", "POST", cacheAs = "plans/${current.id}/grocery")
            } else {
                Api.get("plans/${current.id}/grocery", cache = true)
            }
            if (gen != generation) return
            grocery = list.lines
            Freshness.mark(Freshness.GROCERY)
            loadGroceryPrefs(onlyIfStale = !rebuild)
        } catch (e: Throwable) {
            fail(e)
        }
    }

    suspend fun toggleGrocery(line: GroceryLine) = patchGrocery(line, mapOf("checked" to !line.checked))
    suspend fun setGroceryStore(line: GroceryLine, storeId: String) = patchGrocery(line, mapOf("store" to storeId))
    suspend fun setGroceryAisle(line: GroceryLine, aisleId: String) = patchGrocery(line, mapOf("aisle" to aisleId))
    suspend fun setGroceryQuantity(line: GroceryLine, quantity: String) = patchGrocery(line, mapOf("quantity" to quantity))

    suspend fun patchGrocery(line: GroceryLine, body: Map<String, Any?>) {
        grocery = grocery.map {
            if (it.id != line.id) it else it.copy(
                name = body["custom_text"] as? String ?: it.name,
                checked = body["checked"] as? Boolean ?: it.checked,
                quantity = body["quantity"] as? String ?: it.quantity,
                aisle = body["aisle"] as? String ?: it.aisle,
                store = body["store"] as? String ?: it.store,
            )
        }
        try {
            Api.send<Ok>("grocery/lines/${line.id}", "PATCH", body)
            if (body["custom_text"] != null) reloadGrocery()
        } catch (e: Throwable) {
            fail(e)
            reloadGrocery()
        }
    }

    suspend fun markAllGroceryComplete() = setAllChecked(true)

    suspend fun uncheckAllGrocery() = setAllChecked(false)

    private suspend fun setAllChecked(checked: Boolean) {
        val ids = grocery.filter { it.checked != checked && !it.neverShop }.map { it.id }.toSet()
        if (ids.isEmpty()) return
        grocery = grocery.map { if (it.id in ids) it.copy(checked = checked) else it }
        try {
            for (id in ids) Api.send<Ok>("grocery/lines/$id", "PATCH", mapOf("checked" to checked))
        } catch (e: Throwable) {
            fail(e)
            reloadGrocery()
        }
    }

    suspend fun setPantryFlags(name: String, have: Boolean, neverShop: Boolean) {
        try {
            Api.send<KitchenPantryItem>("pantry/items", "POST", mapOf("name" to name, "have" to have, "never_shop" to neverShop, "zone" to "dry"))
            reloadGrocery()
        } catch (e: Throwable) {
            fail(e)
        }
    }

    suspend fun addSubstitute(from: String, to: String) {
        val dest = to.trim()
        if (dest.isEmpty()) return
        try {
            Api.send<KitchenOverrideList>("overrides", "POST", mapOf("from_name" to from, "to_name" to dest))
            reloadGrocery()
        } catch (e: Throwable) {
            fail(e)
        }
    }

    suspend fun addGroceryLine(name: String, quantity: String, store: String? = null) {
        val names = name.split(",").map { it.trim() }.filter { it.isNotEmpty() }
        val current = plan ?: return
        if (names.isEmpty()) return
        try {
            for (item in names) {
                val line: GroceryLine = Api.send(
                    "plans/${current.id}/grocery/lines", "POST",
                    mapOf("name" to item, "quantity" to quantity.trim(), "store" to (store ?: "")),
                )
                grocery = if (grocery.any { it.id == line.id }) grocery.map { if (it.id == line.id) line else it } else grocery + line
            }
        } catch (e: Throwable) {
            fail(e)
        }
    }

    suspend fun suggestGroceryItems(q: String): List<String> {
        val trimmed = q.trim()
        if (trimmed.isEmpty()) return emptyList()
        return try {
            Api.get<GroceryItemHits>("grocery-items", mapOf("q" to trimmed, "limit" to "8")).items.map { it.name }
        } catch (e: Throwable) {
            fail(e); emptyList()
        }
    }

    suspend fun persistGroceryPrefs() {
        if (!groceryPrefsLoaded) return
        val prefs = mapOf(
            "stores" to stores.map { mapOf("id" to it.id, "name" to it.name) },
            "aisles" to aisles.map { mapOf("id" to it.id, "name" to it.name, "number" to it.number) },
            "groupByStore" to groupByStore,
            "showMeals" to showMeals,
            "hideChecked" to hideChecked,
            "showAisleNums" to showAisleNums,
            "showEmoji" to showEmoji,
        )
        try {
            Api.send<Household>("household", "PUT", mapOf("prefs" to mapOf("grocery" to prefs)), cacheAs = "household")
        } catch (e: Throwable) {
            fail(e)
        }
    }

    fun aisleName(id: String): String =
        aisles.firstOrNull { it.id == id }?.name ?: id.replace("_", " ").capitalizedWords()

    fun aisleTitle(id: String): String {
        val aisle = aisles.firstOrNull { it.id == id } ?: return id.replace("_", " ").capitalizedWords()
        return if (aisle.number.isNotEmpty()) "${aisle.name} · Aisle ${aisle.number}" else aisle.name
    }

    /** `onlyIfStale` (opening Prep) skips the server unless the plan changed. */
    suspend fun loadPrep(onlyIfStale: Boolean = false) {
        if (onlyIfStale && Freshness.isFresh(Freshness.PREP)) return
        val gen = generation
        try {
            val current = currentPlan()
            val box: PrepList = Api.get("plans/${current.id}/prep", cache = true)
            if (gen != generation) return
            prepTasks = box.tasks
            Freshness.mark(Freshness.PREP)
        } catch (e: Throwable) {
            fail(e)
        }
    }

    suspend fun togglePrep(task: PrepTask) {
        val next = !task.done
        // Checking a task checks every item in it.
        prepTasks = prepTasks.map { t ->
            if (t.id != task.id) t else t.copy(done = next, meals = t.meals.map { m -> m.copy(steps = m.steps?.map { it.copy(done = next) }) })
        }
        try {
            Api.send<Ok>("prep/${task.id}", "PATCH", mapOf("done" to next))
        } catch (e: Throwable) {
            fail(e)
        }
        loadPrep()
    }

    /** Thumbs on a meal. A 👎 meal is never suggested again; a 👍 pulls similar meals in. */
    suspend fun rateMeal(slot: PlanSlot, rating: Int) {
        val before = slot.rating ?: 0
        setLocalRating(slot.recipeId, rating)
        try {
            Api.send<MealRating>("recipes/${slot.recipeId}/rating", "PUT", mapOf("rating" to rating))
        } catch (e: Throwable) {
            setLocalRating(slot.recipeId, before)
            fail(e)
        }
    }

    private fun setLocalRating(recipeId: Int, rating: Int) {
        val current = plan ?: return
        plan = current.copy(slots = current.slots.map { if (it.recipeId == recipeId) it.copy(rating = rating) else it })
    }

    /** 👍/👎 on a whole prep item, with an optional reason and note for a 👎. A null note keeps the saved one. */
    suspend fun ratePrepTask(taskId: Int, rating: Int, reason: String = "", note: String? = null) {
        val task = prepTasks.firstOrNull { it.id == taskId } ?: return
        val why = if (rating < 0) reason else ""
        val words = if (rating < 0) (note ?: task.reasonNote ?: "") else ""
        prepTasks = prepTasks.map { if (it.id == taskId) it.copy(rating = rating, reason = why, reasonNote = words) else it }
        try {
            Api.send<Ok>("prep/$taskId/feedback", "PUT", mapOf("rating" to rating, "reason" to why, "note" to words))
        } catch (e: Throwable) {
            prepTasks = prepTasks.map { if (it.id == taskId) it.copy(rating = task.rating, reason = task.reason, reasonNote = task.reasonNote) else it }
            fail(e)
        }
    }

    /** Recipe steps that aren't in Weekend prep, for "Missing a prep step?". null on failure. */
    suspend fun loadMissingPrep(): List<MissingPrepMeal>? = try {
        val current = currentPlan()
        Api.get<MissingPrepList>("plans/${current.id}/prep/missing").meals
    } catch (e: Throwable) {
        fail(e); null
    }

    /** Add a skipped recipe step to Weekend prep (or take it back), with an optional note. */
    suspend fun setMissingPrep(recipeId: Int, key: String, note: String, added: Boolean): Boolean = try {
        val current = currentPlan()
        Api.send<Ok>("plans/${current.id}/prep/missing", "PUT", mapOf("recipe_id" to recipeId, "key" to key, "note" to note, "added" to added))
        loadPrep()
        true
    } catch (e: Throwable) {
        fail(e); false
    }

    fun storeName(line: GroceryLine): String =
        stores.firstOrNull { it.id == line.store }?.name ?: line.store.ifEmpty { "Store" }

    private suspend fun currentPlan(): Plan {
        plan?.let { return it }
        val gen = generation
        val loaded: Plan = Api.get("plans/current", cache = true)
        if (gen != generation) throw CancellationException()
        plan = loaded
        Freshness.mark(Freshness.PLAN)
        return loaded
    }

    /** After a change to the plan: the server has already rebuilt the list, so read it. */
    private suspend fun reloadGrocery() {
        val current = plan ?: return
        val gen = generation
        try {
            val list: GroceryList = Api.get("plans/${current.id}/grocery", cache = true)
            if (gen != generation) return
            grocery = list.lines
            Freshness.mark(Freshness.GROCERY)
        } catch (e: Throwable) {
            fail(e)
        }
    }

    suspend fun loadGroceryPrefs(onlyIfStale: Boolean = false) {
        if (onlyIfStale && Freshness.isFresh(Freshness.HOUSEHOLD) && groceryPrefsLoaded) return
        val gen = generation
        try {
            val hh: Household = Api.get("household", cache = true)
            if (gen != generation) return
            applyHousehold(hh)
            // Only server data counts: saving grocery settings from a stale copy could overwrite another device's stores.
            groceryPrefsLoaded = true
            Freshness.mark(Freshness.HOUSEHOLD)
        } catch (e: Throwable) {
            fail(e)
            groceryPrefsLoaded = false
        }
    }

    private fun applyHousehold(hh: Household) {
        familyPortions = hh.familyPortions
        stores = hh.stores ?: ShopStore.defaults
        aisles = hh.aisles?.takeIf { it.isNotEmpty() } ?: ShopAisle.defaults
        hh.groceryFlag("groupByStore")?.let { groupByStore = it }
        hh.groceryFlag("showMeals")?.let { showMeals = it }
        hh.groceryFlag("hideChecked")?.let { hideChecked = it }
        hh.groceryFlag("showAisleNums")?.let { showAisleNums = it }
        hh.groceryFlag("showEmoji")?.let { showEmoji = it }
    }

    private suspend fun patchSlot(
        id: Int, body: Map<String, Any?>, refreshGrocery: Boolean = false, reloadOnError: Boolean = true,
    ) {
        try {
            val next: PlanSlot = Api.send("slots/$id", "PATCH", body)
            applySlot(next)
            if (refreshGrocery) reloadGrocery()
        } catch (e: Throwable) {
            if (Api.isCancellation(e)) return
            val message = Api.message(e)
            if (reloadOnError) loadAll()
            error = message
        }
    }

    private fun applySlot(next: PlanSlot) {
        val current = plan ?: return
        plan = current.copy(slots = current.slots.map { if (it.id == next.id) next else it })
    }

    private fun applyLocalSlot(id: Int, update: (PlanSlot) -> PlanSlot) {
        val current = plan ?: return
        if (current.slots.none { it.id == id }) return
        plan = current.copy(slots = current.slots.map { if (it.id == id) update(it) else it })
    }

    suspend fun schedule(slot: PlanSlot, date: LocalDate): Boolean {
        error = null
        patchSlot(slot.id, mapOf("scheduled_date" to date.toString()), reloadOnError = false)
        return error == null
    }

    suspend fun markCooked(ids: Set<Int>) {
        for (slot in plan?.slots ?: emptyList()) if (slot.id in ids && !slot.cooked) patchSlot(slot.id, mapOf("cooked" to true))
    }

    suspend fun removeSlots(ids: Set<Int>) {
        for (slot in plan?.slots ?: emptyList()) if (slot.id in ids) removeSlot(slot)
    }

    suspend fun saveDraft(title: String) {
        val current = plan ?: return
        try {
            Api.send<Plan>("plans", "POST", mapOf("title" to title.ifEmpty { "Saved plan" }, "draft" to true, "source_plan_id" to current.id))
        } catch (e: Throwable) {
            fail(e)
        }
    }

    /** "Report a problem with this recipe": why, and the user's note. True when sent. */
    suspend fun reportRecipe(recipeId: Int, reason: String, note: String): Boolean = try {
        Api.send<Ok>("recipes/$recipeId/report", "POST", mapOf("reason" to reason, "note" to note))
        true
    } catch (e: Throwable) {
        fail(e); false
    }

    /** "Report this suggestion": the user's note, saved with why the plan was suggested. */
    suspend fun reportProposal(note: String): Boolean {
        val current = proposal ?: return false
        return try {
            Api.send<Ok>("plans/${current.id}/report", "POST", mapOf("note" to note))
            true
        } catch (e: Throwable) {
            proposalError = Api.message(e); false
        }
    }

    suspend fun reviewProposal(decision: String) {
        val current = proposal ?: return
        proposalError = null
        try {
            val reviewed: Plan = Api.send("plans/${current.id}/decision/$decision", "POST", emptyMap())
            if (decision == "approve") {
                showingProposal = false
                proposal = null
                plan = reviewed
                loadGrocery()
            } else {
                proposal = reviewed
                replaceDeclinedProposal()
            }
        } catch (e: Throwable) {
            proposalError = Api.message(e)
        }
    }

    private suspend fun replaceDeclinedProposal() {
        val current = proposal ?: return
        val suggested = current.suggestedRecipeIds?.size ?: current.slots.size
        val count = maxOf(1, suggested)
        val keep = current.slots.size > suggested
        if (!newPlan(meals = count, keepCurrent = keep)) {
            proposalError = error ?: "Couldn't find another plan. Try again or adjust Settings → Filters."
            error = null
        }
    }

    suspend fun resizeProposal(count: Int) {
        val current = proposal ?: return
        proposalError = null
        try {
            proposal = Api.send("plans/${current.id}/resize", "POST", mapOf("meal_count" to count))
        } catch (e: Throwable) {
            proposalError = Api.message(e)
        }
    }

    suspend fun swapProposal(slot: PlanSlot, recipeId: Int? = null) {
        val current = proposal ?: return
        proposalError = null
        try {
            proposal = Api.send("plans/${current.id}/swap/${slot.id}", "POST", recipeId?.let { mapOf("recipe_id" to it) } ?: emptyMap())
        } catch (e: Throwable) {
            proposalError = Api.message(e)
        }
    }

    /** Resume a saved/in-flight suggestion without issuing another request. */
    suspend fun openSuggestions(keepCurrent: Boolean = false) {
        if (generatingProposal) { showingProposal = true; return }
        val current = proposal
        if (current != null && current.status == "suggested") {
            val suggested = current.suggestedRecipeIds ?: emptyList()
            val kept = current.slots.filter { it.recipeId !in suggested }.map { it.recipeId }.toSet()
            val onPlan = plan?.slots?.map { it.recipeId }?.toSet() ?: emptySet()
            if ((keepCurrent && kept == onPlan) || (!keepCurrent && kept.isEmpty())) {
                proposalError = null
                showingProposal = true
                return
            }
        }
        val count = if (keepCurrent) maxOf(1, 4 - (plan?.slots?.size ?: 0)) else 4
        newPlan(meals = count, keepCurrent = keepCurrent)
    }

    suspend fun newPlan(source: Int? = null, meals: Int? = null, keepCurrent: Boolean = false): Boolean {
        if (meals != null) {
            if (generatingProposal) { showingProposal = true; return false }
            generatingProposal = true
            proposal = null
            proposalError = null
            showingProposal = true
        }
        try {
            error = null
            val body = mutableMapOf<String, Any?>("title" to "This week")
            if (source != null) body["source_plan_id"] = source
            if (meals != null) {
                try {
                    val capabilities: SuggestionCapabilities = Api.get("suggestions/capabilities", reportErrors = false)
                    if (!(capabilities.version >= 2 && capabilities.review && capabilities.resize && capabilities.swap)) {
                        error = "Meal planning is being updated. Please try again after the server update."
                        return false
                    }
                } catch (e: ApiError) {
                    if (e.code == 404 || e.code == 405) {
                        error = "Meal suggestions need the updated server. You can still use your current plan and choose meals yourself."
                        return false
                    }
                    throw e
                }
                body["meal_count"] = meals
            }
            body["keep_current"] = keepCurrent
            val created: Plan = Api.send("plans", "POST", body)
            if (meals != null) {
                if (created.status != "suggested" || created.suggestedRecipeIds == null) {
                    error = "The server returned an incompatible plan. Please update the server before requesting suggestions."
                    return false
                }
                proposalError = null
                proposal = created
            } else {
                plan = created
                loadGrocery()
            }
            error = null
            return true
        } catch (e: Throwable) {
            fail(e)
            return false
        } finally {
            if (meals != null) {
                generatingProposal = false
                error?.let { proposalError = it }
            }
        }
    }
}
