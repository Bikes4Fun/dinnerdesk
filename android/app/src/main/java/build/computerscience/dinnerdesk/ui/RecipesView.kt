package build.computerscience.dinnerdesk.ui

import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.combinedClickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.AddCircle
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.Favorite
import androidx.compose.material.icons.filled.RemoveCircle
import androidx.compose.material.icons.filled.Search
import androidx.compose.material.icons.outlined.AddCircleOutline
import androidx.compose.material.icons.outlined.BookmarkBorder
import androidx.compose.material.icons.outlined.RemoveCircleOutline
import androidx.compose.material.icons.outlined.FavoriteBorder
import androidx.compose.material.icons.outlined.Flag
import androidx.compose.material.icons.outlined.MoreHoriz
import androidx.compose.material.icons.outlined.Visibility
import androidx.compose.material.icons.outlined.VisibilityOff
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import build.computerscience.dinnerdesk.data.Api
import build.computerscience.dinnerdesk.data.Freshness
import build.computerscience.dinnerdesk.data.IngredientLine
import build.computerscience.dinnerdesk.data.InstructionStep
import build.computerscience.dinnerdesk.data.KitchenApi
import build.computerscience.dinnerdesk.data.PantryMatch
import build.computerscience.dinnerdesk.data.RecipeDetail
import build.computerscience.dinnerdesk.data.RecipeReportReason
import build.computerscience.dinnerdesk.data.RecipeSuggestions
import build.computerscience.dinnerdesk.data.RecipeSummary
import build.computerscience.dinnerdesk.data.ResponseCache
import build.computerscience.dinnerdesk.data.scaleAmount
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import java.net.URI
import java.time.LocalDate

private enum class RecipeListKind(val title: String) {
    Suggestions("Suggestions"), Fav("Your Favorites"), TryLater("To try"), Popular("Most Popular"), Mine("Your Recipes"),
    Simple("Super simple"), Sauces("Sauces & dressings"), Hidden("Hidden"), All("All recipes"),
}

private enum class RecipeSearchFilter(val label: String) {
    Fav("Your favorites"), TryLater("To try"), Popular("Popular"), Quick("Quick"), Pantry("Uses pantry"), Hidden("Hidden"),
}

@Composable
fun RecipesView() {
    val store = LocalStore.current
    val nav = LocalNav.current
    val scope = rememberCoroutineScope()
    var suggestedIds by remember { mutableStateOf<List<Int>>(emptyList()) }
    var query by rememberSaveable { mutableStateOf("") }
    var searchOpen by rememberSaveable { mutableStateOf(false) }
    var searchJob by remember { mutableStateOf<Job?>(null) }
    var filters by remember { mutableStateOf(setOf<RecipeSearchFilter>()) }
    var pantryHave by remember { mutableStateOf(setOf<String>()) }
    var hiddenRecipes by remember { mutableStateOf<List<RecipeSummary>>(emptyList()) }
    val searching = query.isNotBlank() || filters.isNotEmpty()

    LaunchedEffect(Unit) { hiddenRecipes = store.loadHiddenRecipes(onlyIfStale = true) }

    val recipes = store.recipes
    val favorites = recipes.filter { it.favorited }
    val toTry = recipes.filter { it.toTry }
    val meals = recipes.filter { it.isMeal }
    val popular = meals.filter { "popular" in it.tags }
    val mine = recipes.filter { !it.catalog }
    val simple = meals.filter { (it.cookingMinutes ?: 99) <= 20 }
    val sauces = recipes.filter { it.isExtra }

    fun rows(kind: RecipeListKind): List<RecipeSummary> = when (kind) {
        RecipeListKind.Suggestions -> suggestedIds.mapNotNull { id -> recipes.firstOrNull { it.id == id } }
        RecipeListKind.Fav -> favorites
        RecipeListKind.TryLater -> toTry
        RecipeListKind.Popular -> popular
        RecipeListKind.Mine -> mine
        RecipeListKind.Simple -> simple
        RecipeListKind.Sauces -> sauces
        RecipeListKind.Hidden -> hiddenRecipes
        RecipeListKind.All -> meals.sortedWith(compareBy(String.CASE_INSENSITIVE_ORDER) { it.name })
    }

    val searchRows = run {
        var rows = if (RecipeSearchFilter.Hidden in filters) hiddenRecipes else recipes
        val q = query.trim().lowercase()
        if (RecipeSearchFilter.Hidden in filters && q.isNotEmpty()) {
            rows = rows.filter { r -> r.name.lowercase().contains(q) || r.ingredients.any { it.lowercase().contains(q) } }
        }
        if (RecipeSearchFilter.Fav in filters) rows = rows.filter { it.favorited }
        if (RecipeSearchFilter.TryLater in filters) rows = rows.filter { it.toTry }
        if (RecipeSearchFilter.Popular in filters) rows = rows.filter { "popular" in it.tags }
        if (RecipeSearchFilter.Quick in filters) rows = rows.filter { (it.cookingMinutes ?: 99) <= 30 }
        if (RecipeSearchFilter.Pantry in filters) rows = rows.filter { PantryMatch.uses(it.ingredients, pantryHave) }
        rows
    }

    fun onQuery(q: String) {
        query = q
        searchJob?.cancel()
        searchJob = scope.launch {
            delay(280)
            if (RecipeSearchFilter.Hidden in filters) hiddenRecipes = store.loadHiddenRecipes() else store.searchRecipes(q)
        }
    }

    Column(Modifier.fillMaxSize().background(Theme.bg)) {
        Row(Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 12.dp), verticalAlignment = Alignment.CenterVertically) {
            Text("Recipes", style = Theme.bigTitle, color = Theme.ink, modifier = Modifier.weight(1f))
            IconAction(Icons.Filled.Search, "Search Recipes") {
                searchOpen = !searchOpen
                if (!searchOpen) {
                    query = ""
                    searchJob?.cancel()
                    store.launch { searchRecipes("") }
                }
            }
        }
        if (searchOpen) {
            TextBox(
                query, ::onQuery,
                store.recipeTotal?.let { "Search $it recipes or ingredients" } ?: "Search recipes or ingredients",
                modifier = Modifier.padding(horizontal = 16.dp).padding(bottom = 12.dp), corner = 10.dp,
            )
        }
        RefreshBox({
            store.searchRecipes(query)
            hiddenRecipes = store.loadHiddenRecipes()
            try { suggestedIds = Api.get<RecipeSuggestions>("suggestions/recipes", reportErrors = false).recipeIds } catch (_: Exception) {}
        }) {
            Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(vertical = 16.dp), verticalArrangement = Arrangement.spacedBy(24.dp)) {
                store.error?.let { ErrorBanner(it, Modifier.padding(horizontal = 16.dp)) }
                Row(Modifier.horizontalScroll(rememberScrollState()).padding(horizontal = 16.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Chip("All", filters.isEmpty()) { filters = emptySet() }
                    for (filter in RecipeSearchFilter.entries) {
                        Chip(filter.label, filter in filters) {
                            filters = if (filter in filters) filters - filter else filters + filter
                            if (filter == RecipeSearchFilter.Hidden) scope.launch { hiddenRecipes = store.loadHiddenRecipes() }
                            if (filter == RecipeSearchFilter.Pantry) scope.launch {
                                try { pantryHave = PantryMatch.have(KitchenApi.pantry()) } catch (_: Exception) {}
                            }
                        }
                    }
                }
                if (searching) {
                    Box(Modifier.padding(horizontal = 16.dp)) { RecipeGrid(searchRows, if (query.isEmpty()) "No recipes" else "No matches") }
                } else {
                    fun open(kind: RecipeListKind) = nav.push(Route.RecipeGrid(kind.title, rows(kind)))
                    if (suggestedIds.isNotEmpty()) BrowseSection("Suggestions", rows(RecipeListKind.Suggestions)) { open(RecipeListKind.Suggestions) }
                    BrowseSection("Your favorites", favorites, empty = "Heart a recipe to keep it here.") { open(RecipeListKind.Fav) }
                    if (toTry.isNotEmpty()) BrowseSection("To try", toTry) { open(RecipeListKind.TryLater) }
                    if (popular.isNotEmpty()) BrowseSection("Most popular", popular) { open(RecipeListKind.Popular) }
                    if (mine.isNotEmpty()) BrowseSection("Your recipes", mine) { open(RecipeListKind.Mine) }
                    if (simple.isNotEmpty()) BrowseSection("Super simple", simple) { open(RecipeListKind.Simple) }
                    if (sauces.isNotEmpty()) BrowseSection("Sauces & dressings", sauces) { open(RecipeListKind.Sauces) }
                    BrowseSection("All recipes", rows(RecipeListKind.All), empty = "No recipes") { open(RecipeListKind.All) }
                }
            }
        }
    }
}

/** A day-stable shuffle so browse rows change daily but don't jump around. */
private fun browseOrder(rows: List<RecipeSummary>): List<RecipeSummary> {
    val seed = LocalDate.now().toEpochDay().toULong()
    fun score(recipe: RecipeSummary): ULong {
        var value = recipe.id.toULong() xor seed
        value = (value xor (value shr 16)) * 0x45d9f3bUL
        return value xor (value shr 16)
    }
    return rows.sortedBy { score(it) }
}

@Composable
private fun BrowseSection(title: String, rows: List<RecipeSummary>, empty: String? = null, seeAll: () -> Unit) {
    val large = isAccessibilitySize
    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Box(Modifier.padding(horizontal = 16.dp)) {
            if (rows.isEmpty()) {
                Text(title, style = Theme.title, color = Theme.ink, modifier = Modifier.semantics { heading() })
            } else if (large) {
                Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
                    Text(title, style = Theme.title, color = Theme.ink, modifier = Modifier.semantics { heading() })
                    LinkButton("See all", Modifier.semantics { contentDescription = "See all $title" }, onClick = seeAll)
                }
            } else {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(title, style = Theme.title, color = Theme.ink, maxLines = 1, overflow = TextOverflow.Ellipsis, modifier = Modifier.weight(1f).semantics { heading() })
                    LinkButton("See all", Modifier.semantics { contentDescription = "See all $title" }, onClick = seeAll)
                }
            }
        }
        if (rows.isEmpty() && empty != null) {
            Text(empty, style = Theme.subtitle, color = Theme.muted, modifier = Modifier.padding(horizontal = 16.dp))
        } else if (rows.isNotEmpty()) {
            val ordered = remember(rows) { browseOrder(rows) }
            LazyRow(contentPadding = androidx.compose.foundation.layout.PaddingValues(horizontal = 16.dp), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                items(ordered, key = { it.id }) { recipe ->
                    Box(Modifier.width(if (large) 280.dp else 160.dp)) { RecipeTile(recipe) }
                }
            }
        }
    }
}

/** Two columns of recipe cards; one at large text sizes so names don't break mid-word. */
@Composable
private fun RecipeGrid(rows: List<RecipeSummary>, empty: String?) {
    if (rows.isEmpty()) {
        if (empty != null) Text(empty, style = Theme.body, color = Theme.muted, modifier = Modifier.fillMaxWidth())
        return
    }
    val columns = if (isAccessibilitySize) 1 else 2
    Column(verticalArrangement = Arrangement.spacedBy(16.dp)) {
        for (row in rows.chunked(columns)) {
            Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                for (recipe in row) Box(Modifier.weight(1f)) { RecipeTile(recipe) }
                repeat(columns - row.size) { Spacer(Modifier.weight(1f)) }
            }
        }
    }
}

@Composable
fun RecipeGridPage(title: String, recipes: List<RecipeSummary>) {
    Column(Modifier.fillMaxSize().background(Theme.bg)) {
        NavBar()
        Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState())) {
            LargeTitle(title)
            Box(Modifier.padding(16.dp)) { RecipeGrid(recipes, "No recipes") }
        }
    }
}

/** Square photo with a this-plan check, bold name underneath. Long-press for favorite / to try / hide. */
@OptIn(ExperimentalFoundationApi::class)
@Composable
fun RecipeTile(recipe: RecipeSummary) {
    val store = LocalStore.current
    val nav = LocalNav.current
    var menu by remember { mutableStateOf(false) }
    val onWeek = store.onWeek(recipe.id)
    Box {
        Column(
            Modifier.fillMaxWidth().clip(RoundedCornerShape(12.dp))
                .combinedClickable(onClick = { nav.push(Route.Recipe(recipe.id)) }, onLongClick = { menu = true }),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            Box(Modifier.fillMaxWidth().aspectRatio(1f).clip(RoundedCornerShape(12.dp))) {
                RecipePhoto(recipe.photoPath, fill = true, corner = 12.dp)
                Box(
                    Modifier.align(Alignment.TopEnd).padding(4.dp).size(44.dp).clip(CircleShape)
                        .clickable { store.launch { toggleWeek(recipe) } }
                        .semantics { contentDescription = if (onWeek) "Remove from this plan" else "Add to this plan" },
                    contentAlignment = Alignment.Center,
                ) {
                    Box(Modifier.size(26.dp).background(Color.White, CircleShape))
                    Icon(
                        if (onWeek) Icons.Filled.CheckCircle else Icons.Filled.AddCircle, null,
                        tint = if (onWeek) Theme.accent else Color.Black.copy(alpha = 0.35f), modifier = Modifier.size(34.dp),
                    )
                }
            }
            RecipeCardName(recipe.name, lineLimit = 3, reservesSpace = true)
        }
        DropdownMenu(expanded = menu, onDismissRequest = { menu = false }, containerColor = Theme.surface) {
            DropdownMenuItem({ Text(if (recipe.favorited) "Unfavorite" else "Favorite", style = Theme.body) }, { menu = false; store.launch { toggleFavorite(recipe) } })
            DropdownMenuItem({ Text(if (onWeek) "Remove from plan" else "Add to plan", style = Theme.body) }, { menu = false; store.launch { toggleWeek(recipe) } })
            DropdownMenuItem({ Text(if (recipe.toTry) "Remove from To try" else "To try", style = Theme.body) }, { menu = false; store.launch { toggleTryLater(recipe) } })
            DropdownMenuItem(
                { Text(if (recipe.hidden) "Unhide recipe" else "Hide recipe", style = Theme.body, color = if (recipe.hidden) Theme.ink else Theme.destructive) },
                { menu = false; store.launch { setHidden(recipe.id, !recipe.hidden) } },
            )
        }
    }
}

private enum class RecipePageTab { Overview, Cook }

@Composable
fun RecipeDetailView(id: Int) {
    val store = LocalStore.current
    val dismiss = LocalDismiss.current
    val openUrl = rememberOpenUrl()
    val scope = rememberCoroutineScope()
    var recipe by remember { mutableStateOf<RecipeDetail?>(null) }
    var error by remember { mutableStateOf<String?>(null) }
    val added = store.onWeek(id)
    var adding by remember { mutableStateOf(false) }
    var planNotice by remember { mutableStateOf<String?>(null) }
    var showingMenu by remember { mutableStateOf(false) }
    var tab by rememberSaveable { mutableStateOf(RecipePageTab.Overview) }
    var nameExpanded by remember { mutableStateOf(false) }
    var draftServings by remember { mutableStateOf<Int?>(null) }
    var reporting by remember { mutableStateOf(false) }
    var reported by remember { mutableStateOf(false) }
    val admin = store.isAdmin

    val mealServings = store.plan?.slots?.firstOrNull { it.recipeId == id }?.servings
        ?: draftServings ?: store.familyPortions ?: recipe?.servings ?: 4

    LaunchedEffect(id) {
        // Show the saved recipe at once; ask the server only when there is none or it's old.
        val key = ResponseCache.key("recipes/$id")
        if (recipe == null) recipe = Api.cached<RecipeDetail>("recipes/$id")
        val age = ResponseCache.age(key) ?: Double.MAX_VALUE
        if (recipe == null || age > Freshness.RECIPE_AGE) {
            try {
                recipe = Api.get<RecipeDetail>("recipes/$id", cache = true)
            } catch (e: Throwable) {
                // With a saved copy on screen (e.g. no signal in the store), keep showing it.
                if (recipe == null && !Api.isCancellation(e)) error = Api.message(e)
            }
        }
        store.loadGroceryPrefs(onlyIfStale = true)
    }
    LaunchedEffect(Unit) { store.loadAdmin() }
    LaunchedEffect(planNotice) {
        if (planNotice == null) return@LaunchedEffect
        delay(2000)
        planNotice = null
    }

    fun addToWeek() {
        if (adding) return
        val removing = added
        error = null
        planNotice = null
        adding = true
        scope.launch {
            if (removing) store.removeFromWeek(id) else store.addToWeek(id, draftServings)
            if (store.onWeek(id) != removing) planNotice = if (removing) "Removed from this plan" else "Added to this plan"
            else error = store.error
            adding = false
        }
    }

    fun bumpServings(delta: Int) {
        val next = (mealServings + delta).coerceIn(1, 50)
        if (next == mealServings) return
        if (store.onWeek(id)) store.launch { setServingsForRecipe(id, next) } else draftServings = next
    }

    fun togglePrep(index: Int) {
        val current = recipe ?: return
        if (index !in current.instructions.indices) return
        val steps = current.instructions.toMutableList()
        steps[index] = steps[index].copy(prep = !(steps[index].prep ?: false))
        val next = current.copy(instructions = steps)
        recipe = next
        scope.launch {
            try {
                recipe = Api.send<RecipeDetail>("recipes/$id", "PATCH", mapOf("in_place" to true, "instructions" to steps.map { it.asBody() }), cacheAs = "recipes/$id")
            } catch (e: Throwable) {
                error = Api.message(e)
            }
        }
    }

    Box(Modifier.fillMaxSize().background(Theme.bg)) {
        Column(Modifier.fillMaxSize()) {
            NavBar(actions = {
                val r = recipe
                if (r != null) {
                    IconAction(if (added) Icons.Filled.RemoveCircle else Icons.Filled.AddCircle, if (added) "Remove from this plan" else "Add to this plan", enabled = !adding) { addToWeek() }
                    IconAction(if (r.favorited) Icons.Filled.Favorite else Icons.Outlined.FavoriteBorder, if (r.favorited) "Unfavorite" else "Favorite", tint = if (r.favorited) Theme.accent else Theme.muted) {
                        scope.launch { store.setFavorite(r.id, !r.favorited)?.let { recipe = it } }
                    }
                    IconAction(Icons.Outlined.MoreHoriz, "Recipe options") { showingMenu = true }
                }
            })
            val r = recipe
            when {
                r != null -> Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
                    Segmented(listOf(RecipePageTab.Overview to "Overview", RecipePageTab.Cook to "Cook"), tab) { tab = it }
                    if (tab == RecipePageTab.Overview) {
                        RecipePhoto(r.photoPath, large = true)
                        if (r.photoAI && r.photoPath != null) StarTip("recipes.ai-photo")
                        else if (r.photoShared && r.photoPath != null) StarTip("recipes.shared-photo")
                    }
                    // Long names at large text sizes pushed everything else off screen. Cap at 3 lines; tap to see it all.
                    Text(
                        r.name, style = Theme.recipeTitle, color = Theme.ink, maxLines = if (nameExpanded) Int.MAX_VALUE else 3,
                        overflow = TextOverflow.Ellipsis,
                        modifier = Modifier.fillMaxWidth().clickable { nameExpanded = !nameExpanded }.semantics { heading(); contentDescription = r.name },
                    )
                    ServingsRow(mealServings, r.cookingMinutes, ::bumpServings)
                    if (tab == RecipePageTab.Overview && r.prettyTags.isNotEmpty()) Text(r.prettyTags, style = Theme.subtitle, color = Theme.muted)
                    if (tab == RecipePageTab.Overview) {
                        Text("Ingredients", style = Theme.title, color = Theme.ink)
                        Column {
                            r.ingredients.forEachIndexed { i, ing ->
                                if (i > 0) Hairline()
                                IngredientRow(ing, scaleAmount(ing.quantity ?: "", r.servings, mealServings))
                            }
                        }
                    } else {
                        Text("Steps", style = Theme.title, color = Theme.ink)
                        if (r.instructionsCustomized) Text("Instructions customized by Dinnerdesk", style = Theme.subtitle, color = Theme.muted)
                        r.sourceLink?.let { link ->
                            val host = try { URI(link).host?.removePrefix("www.") ?: "" } catch (_: Exception) { "" }
                            Text(
                                "${if (r.instructionsSource == "import") "Steps from" else "Source:"} $host", style = Theme.subtitle, color = Theme.accent,
                                modifier = Modifier.clickable { openUrl(link) },
                            )
                        }
                        r.instructions.forEachIndexed { i, step -> CookStepRow(i, step, if (admin) ({ togglePrep(i) }) else null) }
                    }
                    FilledButton(
                        if (added) "Remove from this plan" else "Add to this plan", color = Theme.accent, textColor = Color.White,
                        enabled = !adding, minHeight = 44.dp, shape = RoundedCornerShape(10.dp),
                    ) { addToWeek() }
                }
                error != null -> Box(Modifier.padding(16.dp)) { ErrorBanner(error!!) }
                else -> Spinner()
            }
        }
        planNotice?.let { Notice(it, Modifier.align(Alignment.BottomCenter)) }
    }

    val r = recipe
    if (showingMenu && r != null) {
        MenuSheet(onDismiss = { showingMenu = false }, items = buildList {
            add(MenuItem(if (r.toTry) "Remove from To try" else "To try", Icons.Outlined.BookmarkBorder) {
                scope.launch { store.setTryLater(r.id, !r.toTry)?.let { recipe = it } }
            })
            add(MenuItem(if (r.hidden) "Unhide recipe" else "Hide recipe", if (r.hidden) Icons.Outlined.Visibility else Icons.Outlined.VisibilityOff, destructive = !r.hidden) {
                val on = !r.hidden
                scope.launch { store.setHidden(id, on)?.let { recipe = it; if (on) dismiss() } }
            })
            if (r.catalog) add(MenuItem(if (reported) "Reported. Thanks" else "Report a problem", Icons.Outlined.Flag) {
                if (!reported) reporting = true
            })
        })
    }
    if (reporting) {
        Sheet(onDismiss = { reporting = false }) {
            ReportRecipeSheet(id) { reported = true; reporting = false; planNotice = "Thanks. We'll take a look." }
        }
    }
}

@Composable
private fun ServingsRow(servings: Int, minutes: Int?, bump: (Int) -> Unit) {
    val content: @Composable () -> Unit = {
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(2.dp)) {
            IconAction(Icons.Outlined.RemoveCircleOutline, "Decrease servings", size = 22.dp, enabled = servings > 1) { bump(-1) }
            Text("$servings servings", style = Theme.body, color = Theme.muted, maxLines = 1)
            IconAction(Icons.Outlined.AddCircleOutline, "Increase servings", size = 22.dp, enabled = servings < 50) { bump(1) }
        }
        if (minutes != null) Text("$minutes min", style = Theme.body, color = Theme.muted, maxLines = 1)
    }
    if (isAccessibilitySize) Column(verticalArrangement = Arrangement.spacedBy(8.dp)) { content() }
    else Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(16.dp)) { content() }
}

@Composable
private fun IngredientRow(ing: IngredientLine, qty: String) {
    val large = isAccessibilitySize
    if (large) {
        Column(Modifier.fillMaxWidth().padding(vertical = 8.dp), verticalArrangement = Arrangement.spacedBy(2.dp)) {
            if (qty.isNotEmpty()) Text(qty, style = Theme.count, color = Theme.muted)
            Text(ing.name, style = Theme.body, color = Theme.ink)
        }
    } else {
        Row(Modifier.fillMaxWidth().padding(vertical = 8.dp), horizontalArrangement = Arrangement.spacedBy(12.dp), verticalAlignment = Alignment.Top) {
            if (qty.isNotEmpty()) Text(qty, style = Theme.count, color = Theme.muted, maxLines = 1, modifier = Modifier.padding(top = 3.dp))
            Text(ing.name, style = Theme.body, color = Theme.ink, modifier = Modifier.weight(1f))
        }
    }
}

@Composable
private fun CookStepRow(index: Int, step: InstructionStep, onPrep: (() -> Unit)?) {
    Column(Modifier.fillMaxWidth().padding(bottom = 8.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Text("${index + 1}.", style = Theme.body, color = Theme.accent)
            if (onPrep != null) {
                val on = step.prep ?: false
                Text(
                    "Prep", style = Theme.chipLabel, color = if (on) Color.White else Theme.muted,
                    modifier = Modifier.clip(CircleShape).background(if (on) Theme.accent else Theme.surface).clickable(onClick = onPrep).padding(horizontal = 8.dp, vertical = 4.dp),
                )
            }
        }
        val text = step.displayText
        val lines = text.split("\n")
        val first = lines.firstOrNull()
        if (first != null && first.endsWith(":") && first.length <= 70) {
            Text(first, style = Theme.action, color = Theme.ink)
            if (lines.size > 1) Text(lines.drop(1).joinToString("\n"), style = Theme.body, color = Theme.ink)
        } else {
            Text(text, style = Theme.body, color = Theme.ink, modifier = Modifier.fillMaxWidth())
        }
        val ings = step.ings
        if (!ings.isNullOrEmpty()) {
            Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
                for (line in amountLines(ings)) Text(line, style = Theme.subtitle, color = Theme.muted)
            }
        }
    }
}

private fun amountLines(text: String): List<String> =
    text.replace("\r\n", "\n").split("\n").map { it.trim() }.filter { it.isNotEmpty() }
        .map { if (it.startsWith("- ") || it.startsWith("• ")) it else "· $it" }

/** Why the recipe is wrong, in the user's words. */
@Composable
private fun ReportRecipeSheet(id: Int, onSent: () -> Unit) {
    val store = LocalStore.current
    val scope = rememberCoroutineScope()
    var reason by remember { mutableStateOf<RecipeReportReason?>(null) }
    var note by remember { mutableStateOf("") }
    var sending by remember { mutableStateOf(false) }
    Column(Modifier.fillMaxSize().background(Theme.bg)) {
        SheetBar("Report a problem")
        Column(Modifier.verticalScroll(rememberScrollState()).padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Text("What's wrong?", style = Theme.action, color = Theme.ink)
            for (option in RecipeReportReason.entries) {
                RadioRow(reason == option, { reason = option }) { Text(option.label, style = Theme.body, color = Theme.ink) }
            }
            Text("Anything to add? (optional)", style = Theme.action, color = Theme.ink)
            TextBox(note, { note = it }, "e.g. Step 4 says to add the cream but it's not in the ingredients", style = Theme.subtitle, minLines = 3)
            FilledButton(if (sending) "Sending…" else "Send report", enabled = reason != null && !sending) {
                val picked = reason ?: return@FilledButton
                sending = true
                scope.launch {
                    val sent = store.reportRecipe(id, picked.id, note.trim())
                    sending = false
                    if (sent) onSent()
                }
            }
        }
    }
}
