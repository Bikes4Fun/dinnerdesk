package build.computerscience.dinnerdesk.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowForward
import androidx.compose.material.icons.automirrored.outlined.Assignment
import androidx.compose.material.icons.automirrored.outlined.List
import androidx.compose.material.icons.filled.Cancel
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.Search
import androidx.compose.material.icons.outlined.Book
import androidx.compose.material.icons.outlined.CheckCircleOutline
import androidx.compose.material.icons.outlined.Gesture
import androidx.compose.material.icons.outlined.Group
import androidx.compose.material.icons.outlined.Inventory2
import androidx.compose.material.icons.outlined.Kitchen
import androidx.compose.material.icons.outlined.Replay
import androidx.compose.material.icons.outlined.Settings
import androidx.compose.material.icons.outlined.Storefront
import androidx.compose.material.icons.outlined.SwapHoriz
import androidx.compose.material.icons.outlined.Tune
import androidx.compose.material.icons.outlined.VisibilityOff
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.focus.onFocusChanged
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardCapitalization
import androidx.compose.ui.unit.dp
import build.computerscience.dinnerdesk.data.Api
import build.computerscience.dinnerdesk.data.ItemPlacement
import build.computerscience.dinnerdesk.data.KitchenApi
import build.computerscience.dinnerdesk.data.KitchenDefaults
import build.computerscience.dinnerdesk.data.KitchenOverride
import build.computerscience.dinnerdesk.data.KitchenPantryItem
import build.computerscience.dinnerdesk.data.Ok
import build.computerscience.dinnerdesk.data.RecipeSummary
import build.computerscience.dinnerdesk.data.ShopAisle
import build.computerscience.dinnerdesk.data.ShopStore
import build.computerscience.dinnerdesk.data.bool
import build.computerscience.dinnerdesk.data.int
import kotlinx.coroutines.async
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

/** Everything that isn't Plan, Recipes or Grocery: one list of grey-icon rows. */
@Composable
fun MoreView() {
    val session = LocalSession.current
    val nav = LocalNav.current
    Column(Modifier.fillMaxSize().background(Theme.bg)) {
        ThemeList {
            LargeTitle("More")
            ListRow({ nav.push(Route.PrepHome) }) { ThemeIconRow("Weekend prep", Icons.AutoMirrored.Outlined.Assignment) }
            ListRow({ nav.push(Route.Kitchen) }) { ThemeIconRow("My Kitchen and Groceries", Icons.Outlined.Kitchen) }
            ListRow({ nav.push(Route.TasteLab()) }) { ThemeIconRow("Taste Lab", Icons.Outlined.Gesture) }
            ListRow({ session.showTour = true }, chevron = false) { ThemeIconRow("Quick start tour", Icons.Outlined.Replay) }
            ListRow({ nav.push(Route.Settings) }) { ThemeIconRow("Settings", Icons.Outlined.Settings) }
        }
    }
}

/** My kitchen: portions, pantry, and the grocery settings. */
@Composable
fun KitchenView() {
    val nav = LocalNav.current
    val scope = rememberCoroutineScope()
    var portions by remember { mutableStateOf(4) }
    var savedPortions by remember { mutableStateOf<Int?>(null) }
    var error by remember { mutableStateOf<String?>(null) }

    suspend fun load() {
        try {
            val prefs = KitchenApi.prefs()
            val n = prefs.int("family_portions")?.takeIf { it >= 1 } ?: portions
            savedPortions = n
            portions = n
            error = null
        } catch (e: Throwable) {
            if (!Api.isCancellation(e)) error = Api.message(e)
        }
    }
    LaunchedEffect(Unit) { load() }

    fun setPortions(value: Int) {
        portions = value
        if (savedPortions == null || savedPortions == value) return
        scope.launch {
            try {
                KitchenApi.savePrefs(mapOf("family_portions" to value))
                savedPortions = value
            } catch (e: Throwable) {
                error = Api.message(e)
            }
        }
    }

    Column(Modifier.fillMaxSize().background(Theme.bg)) {
        NavBar()
        ThemeList({ load() }) {
            LargeTitle("My Kitchen and Groceries")
            error?.let { Box(Modifier.padding(16.dp)) { ErrorBanner(it) } }
            ListHeader("Cooking")
            ListRow {
                if (isAccessibilitySize) {
                    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        ThemeIconRow("Family portions", Icons.Outlined.Group, "$portions")
                        Box(Modifier.padding(start = 40.dp)) { Stepper(portions, 1..50, "Family portions", ::setPortions) }
                    }
                } else {
                    Box(Modifier.weight(1f)) { ThemeIconRow("Family portions", Icons.Outlined.Group, "$portions") }
                    Box(Modifier.padding(start = 14.dp)) { Stepper(portions, 1..50, "Family portions", ::setPortions) }
                }
            }
            ListRow({ nav.push(Route.Pantry) }) { ThemeIconRow("Pantry", Icons.Outlined.Inventory2) }
            ListHeader("Grocery list")
            ListRow({ nav.push(Route.AlwaysChecked) }) { ThemeIconRow("Always checked off", Icons.Outlined.CheckCircleOutline) }
            ListRow({ nav.push(Route.Substitutions) }) { ThemeIconRow("Substitutions", Icons.Outlined.SwapHoriz) }
            ListRow({ nav.push(Route.GroceryStores) }) { ThemeIconRow("Stores & aisles", Icons.Outlined.Storefront) }
            ListHeader("Recipes")
            ListRow({ nav.push(Route.Filters) }) { ThemeIconRow("Filters", Icons.Outlined.Tune) }
            ListRow({ nav.push(Route.HiddenRecipes) }) { ThemeIconRow("Hidden recipes", Icons.Outlined.VisibilityOff) }
            ListRow({ nav.push(Route.MyRecipes) }) { ThemeIconRow("My recipes", Icons.Outlined.Book) }
            ListRow { ThemeIconRow("Recipe templates", Icons.AutoMirrored.Outlined.List, "Coming soon") }
        }
    }
}

/** "Buy this instead of that": a recipe's item is swapped on the grocery list. */
@Composable
fun SubstitutionsView() {
    val store = LocalStore.current
    val scope = rememberCoroutineScope()
    var items by remember { mutableStateOf<List<KitchenOverride>>(emptyList()) }
    var from by remember { mutableStateOf("") }
    var to by remember { mutableStateOf("") }
    var error by remember { mutableStateOf<String?>(null) }
    val canAdd = from.isNotBlank() && to.isNotBlank()

    suspend fun load() {
        try { items = KitchenApi.overrides(); error = null } catch (e: Throwable) { if (!Api.isCancellation(e)) error = Api.message(e) }
    }
    LaunchedEffect(Unit) { load() }

    Column(Modifier.fillMaxSize().background(Theme.bg)) {
        NavBar("Substitutions")
        ThemeList({ load() }) {
            error?.let { Box(Modifier.padding(16.dp)) { ErrorBanner(it) } }
            Box(Modifier.padding(horizontal = 20.dp, vertical = 8.dp)) { StarTip("kitchen.substitutions") }
            ListHeader("Your substitutions")
            if (items.isEmpty()) ListRow { Text("None yet", style = Theme.body, color = Theme.muted) }
            for (item in items) {
                androidx.compose.runtime.key(item.id) {
                    SwipeToDelete(item.id, onDelete = {
                        items = items.filter { it.id != item.id }
                        scope.launch {
                            try { items = KitchenApi.deleteOverride(item.id); store.loadGrocery() } catch (e: Throwable) { error = Api.message(e); load() }
                        }
                    }) {
                        ListRow {
                            Row(
                                Modifier.semantics(mergeDescendants = true) { contentDescription = "${item.fromName} becomes ${item.toName}" },
                                verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp),
                            ) {
                                Text(item.fromName, style = Theme.body, color = Theme.muted)
                                Icon(Icons.AutoMirrored.Filled.ArrowForward, null, tint = Theme.muted, modifier = Modifier.size(18.dp))
                                Text(item.toName, style = Theme.mealName, color = Theme.ink)
                            }
                        }
                    }
                }
            }
            ListHeader("Add one")
            ListRow { FormField(from, { from = it }, "Recipe says (e.g. vegetable oil)", KeyboardOptions(capitalization = KeyboardCapitalization.None)) }
            ListRow { FormField(to, { to = it }, "Buy instead (e.g. olive oil)", KeyboardOptions(capitalization = KeyboardCapitalization.None)) }
            ThemeAddRow("Add substitution", enabled = canAdd) {
                scope.launch {
                    try {
                        items = KitchenApi.addOverride(from.trim(), to.trim())
                        from = ""
                        to = ""
                        error = null
                        store.loadGrocery()
                    } catch (e: Throwable) {
                        error = Api.message(e)
                    }
                }
            }
        }
    }
}

/** Recipes hidden from browse. Tap Unhide to bring one back. */
@Composable
fun HiddenRecipesView() {
    val store = LocalStore.current
    val nav = LocalNav.current
    var recipes by remember { mutableStateOf<List<RecipeSummary>>(emptyList()) }
    var loaded by remember { mutableStateOf(false) }
    suspend fun load() { recipes = store.loadHiddenRecipes(); loaded = true }
    LaunchedEffect(Unit) { load() }
    Column(Modifier.fillMaxSize().background(Theme.bg)) {
        NavBar("Hidden recipes")
        ThemeList({ load() }) {
            Text(
                "Recipes you hid from Recipes. They stay out of browse and search until you unhide them.",
                style = Theme.subtitle, color = Theme.muted, modifier = Modifier.padding(horizontal = 20.dp, vertical = 12.dp),
            )
            if (loaded && recipes.isEmpty()) Text("Nothing hidden", style = Theme.body, color = Theme.muted, modifier = Modifier.padding(horizontal = 20.dp))
            for (recipe in recipes) {
                ListRow(chevron = false) {
                    Row(Modifier.weight(1f).clickable { nav.push(Route.Recipe(recipe.id)) }, verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                        RecipePhoto(recipe.photoPath, corner = 10.dp)
                        Text(recipe.name, style = Theme.rowTitle, color = Theme.ink, maxLines = 2)
                    }
                    Text(
                        "Unhide", style = Theme.action, color = Theme.ink,
                        modifier = Modifier.background(Theme.chip, CircleShape).clickable {
                            recipes = recipes.filter { it.id != recipe.id }
                            store.launch { setHidden(recipe.id, false) }
                        }.padding(horizontal = 12.dp, vertical = 6.dp),
                    )
                }
            }
        }
    }
}

/** What you already have. Optional: start every pantry item checked off on the grocery list. */
@Composable
fun PantryView() {
    val store = LocalStore.current
    val nav = LocalNav.current
    val scope = rememberCoroutineScope()
    var items by remember { mutableStateOf<List<KitchenPantryItem>>(emptyList()) }
    var stores by remember { mutableStateOf(ShopStore.defaults) }
    var aisles by remember { mutableStateOf(ShopAisle.defaults) }
    var autoCheck by remember { mutableStateOf(false) }
    var adding by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }

    suspend fun load() {
        try {
            coroutineScope {
                val pantryBox = async { KitchenApi.pantry() }
                val prefs = KitchenApi.prefs()
                items = pantryBox.await().filter { it.have }
                stores = KitchenDefaults.stores(prefs)
                aisles = KitchenDefaults.aisles(prefs)
                autoCheck = prefs.bool("pantry_auto_check") ?: false
            }
            error = null
        } catch (e: Throwable) {
            if (!Api.isCancellation(e)) error = Api.message(e)
        }
    }
    LaunchedEffect(Unit) { load() }

    fun placeText(item: KitchenPantryItem): String? {
        if (item.store == null && item.aisle == null) return null
        val s = stores.firstOrNull { it.id == item.store }?.name ?: "Any store"
        val a = aisles.firstOrNull { it.id == (item.aisle ?: "other") }?.name ?: "Other"
        return "$s, $a"
    }

    Column(Modifier.fillMaxSize().background(Theme.bg)) {
        NavBar("Pantry")
        ThemeList({ load() }) {
            error?.let { Box(Modifier.padding(16.dp)) { ErrorBanner(it) } }
            ThemeAddRow("Add item") { adding = true }
            SwitchRow("Always check off pantry items", autoCheck, style = Theme.mealName) { on ->
                autoCheck = on
                scope.launch {
                    try {
                        KitchenApi.savePrefs(mapOf("pantry_auto_check" to on))
                        store.loadGrocery()
                    } catch (e: Throwable) {
                        autoCheck = !on
                        error = Api.message(e)
                    }
                }
            }
            // The tip sits right under the toggle it explains, outside its tap target.
            Box(Modifier.padding(horizontal = 20.dp, vertical = 8.dp)) { StarTip("kitchen.pantry-auto-check") }
            ListHeader("In your pantry · ${items.size}")
            if (items.isEmpty()) ListRow { Text("Nothing here yet.", style = Theme.body, color = Theme.muted) }
            for (item in items) {
                androidx.compose.runtime.key(item.name) {
                    SwipeToDelete(item.name, onDelete = {
                        items = items.filter { it.name != item.name }
                        val id = item.id
                        if (id != null) scope.launch {
                            try { KitchenApi.patchPantry(id, have = false, neverShop = false); store.loadGrocery() } catch (e: Throwable) { error = Api.message(e); load() }
                        }
                    }) {
                        ListRow({ nav.push(Route.PantryItem(item) { load() }) }) {
                            Column(Modifier.weight(1f).padding(vertical = 4.dp), verticalArrangement = Arrangement.spacedBy(2.dp)) {
                                Text(item.name, style = Theme.mealName, color = Theme.ink, maxLines = 2)
                                if (item.quantity.isNotEmpty()) Text(item.quantity, style = Theme.subtitle, color = Theme.muted)
                                placeText(item)?.let { Text(it, style = Theme.subtitle, color = Theme.muted, maxLines = 1) }
                            }
                            if (item.neverShop || autoCheck) {
                                Icon(Icons.Filled.CheckCircle, "Checked off on the grocery list", tint = Theme.muted.copy(alpha = 0.6f))
                            }
                        }
                    }
                }
            }
        }
    }
    if (adding) {
        Sheet(onDismiss = { adding = false }) {
            KitchenItemPicker("Add to pantry") { name ->
                try {
                    KitchenApi.upsertPantry(name, have = true, neverShop = false)
                    load()
                    store.loadGrocery()
                } catch (e: Throwable) {
                    error = Api.message(e)
                }
            }
        }
    }
}

/** Items you always have (salt, oil). They stay on the grocery list, already checked off. */
@Composable
fun AlwaysCheckedView() {
    val store = LocalStore.current
    val scope = rememberCoroutineScope()
    var items by remember { mutableStateOf<List<KitchenPantryItem>>(emptyList()) }
    var adding by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }

    suspend fun load() {
        try { items = KitchenApi.pantry().filter { it.neverShop }; error = null } catch (e: Throwable) { if (!Api.isCancellation(e)) error = Api.message(e) }
    }
    LaunchedEffect(Unit) { load() }

    Column(Modifier.fillMaxSize().background(Theme.bg)) {
        NavBar("Always checked off")
        ThemeList({ load() }) {
            error?.let { Box(Modifier.padding(16.dp)) { ErrorBanner(it) } }
            Box(Modifier.padding(horizontal = 20.dp, vertical = 8.dp)) { StarTip("kitchen.always-checked") }
            ListHeader("Always checked off · ${items.size}")
            if (items.isEmpty()) {
                ListRow {
                    Column(Modifier.alpha(0.5f), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                        for (line in listOf("Examples — add the items you always keep on hand", "Salt", "Olive oil", "Black pepper")) Text(line, style = Theme.body, color = Theme.muted)
                    }
                }
            }
            for (item in items) {
                androidx.compose.runtime.key(item.name) {
                    SwipeToDelete(item.name, onDelete = {
                        items = items.filter { it.name != item.name }
                        val id = item.id
                        if (id != null) scope.launch {
                            try { KitchenApi.patchPantry(id, neverShop = false); store.loadGrocery() } catch (e: Throwable) { error = Api.message(e); load() }
                        }
                    }) {
                        ListRow { Text(item.name, style = Theme.mealName, color = Theme.ink) }
                    }
                }
            }
            ThemeAddRow("Add item") { adding = true }
        }
    }
    if (adding) {
        Sheet(onDismiss = { adding = false }) {
            KitchenItemPicker("Always check off") { name ->
                try {
                    KitchenApi.upsertPantry(name, have = true, neverShop = true)
                    load()
                    store.loadGrocery()
                } catch (e: Throwable) {
                    error = Api.message(e)
                }
            }
        }
    }
}

/** Search the grocery catalog and pick one item (or keep what you typed). Return picks the first result. */
@Composable
fun KitchenItemPicker(title: String, onPick: suspend (String) -> Unit) {
    val dismiss = LocalDismiss.current
    val scope = rememberCoroutineScope()
    var query by remember { mutableStateOf("") }
    var hits by remember { mutableStateOf<List<String>>(emptyList()) }
    var searchError by remember { mutableStateOf<String?>(null) }
    var picking by remember { mutableStateOf(false) }
    val focus = remember { FocusRequester() }

    LaunchedEffect(Unit) { focus.requestFocus() }
    LaunchedEffect(query) {
        val q = query.trim()
        if (q.isEmpty()) { hits = emptyList(); return@LaunchedEffect }
        delay(250)
        try {
            hits = KitchenApi.searchItems(q)
            searchError = null
        } catch (e: Throwable) {
            if (Api.isCancellation(e)) throw e
            hits = emptyList()
            searchError = Api.message(e)
        }
    }

    fun pick(name: String) {
        if (picking) return
        picking = true
        scope.launch { onPick(name); dismiss() }
    }

    Column(Modifier.fillMaxSize().background(Theme.bg)) {
        SheetBar(title)
        TextBox(
            query, { query = it }, "Search items",
            modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp).focusRequester(focus),
            keyboard = KeyboardOptions(capitalization = KeyboardCapitalization.None, autoCorrectEnabled = false, imeAction = ImeAction.Done),
            actions = KeyboardActions(onDone = { hits.firstOrNull()?.let(::pick) }),
            leading = { Icon(Icons.Filled.Search, null, tint = Theme.muted, modifier = Modifier.size(20.dp)) },
            trailing = if (query.isNotEmpty()) ({ IconAction(Icons.Filled.Cancel, "Clear search", tint = Theme.muted, size = 20.dp) { query = ""; focus.requestFocus() } }) else null,
        )
        Box(Modifier.fillMaxSize()) {
            LazyColumn(Modifier.fillMaxSize()) {
                itemsIndexed(hits, key = { _, name -> name }) { _, name ->
                    Column(Modifier.fillMaxWidth().clickable(enabled = !picking) { pick(name) }) {
                        Box(Modifier.fillMaxWidth().heightIn(min = 56.dp).padding(horizontal = 20.dp), contentAlignment = Alignment.CenterStart) {
                            Text(name, style = Theme.mealName, color = Theme.ink)
                        }
                        Hairline(start = 20.dp)
                    }
                }
            }
            val err = searchError
            if (err != null) Box(Modifier.padding(16.dp)) { ErrorBanner(err) }
            else if (hits.isEmpty()) Text(
                if (query.isEmpty()) "Type an item, like garlic or rice." else "No matches", style = Theme.body, color = Theme.muted,
                modifier = Modifier.align(Alignment.Center),
            )
        }
    }
}

@Composable
fun PantryItemEditor(item: KitchenPantryItem, onChanged: suspend () -> Unit) {
    val store = LocalStore.current
    val dismiss = LocalDismiss.current
    val scope = rememberCoroutineScope()
    var quantity by remember { mutableStateOf(item.quantity) }
    var have by remember { mutableStateOf(item.have) }
    var neverShop by remember { mutableStateOf(item.neverShop) }
    var placement by remember { mutableStateOf<ItemPlacement?>(null) }
    var ready by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }

    LaunchedEffect(Unit) {
        try {
            placement = KitchenApi.placements().firstOrNull { it.name.lowercase() == item.name.lowercase() }
            ready = true
        } catch (e: Throwable) {
            if (!Api.isCancellation(e)) error = Api.message(e)
        }
    }

    fun save(have: Boolean? = null, neverShop: Boolean? = null, quantity: String? = null) {
        val id = item.id ?: return
        store.launch {
            try { KitchenApi.patchPantry(id, have, neverShop, quantity); loadGrocery() } catch (e: Throwable) { error = Api.message(e) }
        }
    }

    fun setPlace(storeId: String? = null, aisleId: String? = null) {
        val current = placement ?: return
        scope.launch {
            try {
                KitchenApi.setPlacement(current, storeId, aisleId)
                placement = current.copy(store = storeId ?: current.store, aisle = aisleId ?: current.aisle)
                store.loadGrocery()
            } catch (e: Throwable) {
                error = Api.message(e)
            }
        }
    }

    val latestQuantity = androidx.compose.runtime.rememberUpdatedState(quantity)
    val latestReady = androidx.compose.runtime.rememberUpdatedState(ready)
    DisposableCleanup {
        if (latestReady.value) store.launch {
            if (latestQuantity.value != item.quantity) item.id?.let { try { KitchenApi.patchPantry(it, quantity = latestQuantity.value); loadGrocery() } catch (_: Exception) {} }
            onChanged()
        }
    }

    Column(Modifier.fillMaxSize().background(Theme.bg)) {
        NavBar(item.name)
        Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState())) {
            FormSection {
                error?.let { Box(Modifier.padding(vertical = 8.dp)) { ErrorBanner(it) } }
                FormSwitch("Have this item", have) { have = it; if (ready) save(have = it) }
                Hairline()
                FormSwitch("Always check off", neverShop) { neverShop = it; if (ready) save(neverShop = it) }
                Hairline()
                FormField(
                    quantity, { quantity = it }, "Amount (optional)",
                    keyboard = KeyboardOptions(imeAction = ImeAction.Done), actions = KeyboardActions(onDone = { save(quantity = quantity) }),
                    modifier = Modifier.onFocusChanged { if (ready && !it.isFocused && quantity != item.quantity) save(quantity = quantity) },
                )
                placement?.let { p ->
                    Hairline()
                    PickerRow("Store", store.stores.firstOrNull { it.id == p.store }?.name ?: "Not set", listOf("" to "Not set") + store.stores.map { it.id to it.name }) { setPlace(storeId = it) }
                    Hairline()
                    PickerRow("Aisle", store.aisles.firstOrNull { it.id == p.aisle }?.name ?: "Other", store.aisles.map { it.id to it.name }) { setPlace(aisleId = it) }
                }
                Hairline()
                Box(
                    Modifier.fillMaxWidth().heightIn(min = 44.dp).clickable {
                        val id = item.id ?: return@clickable
                        scope.launch {
                            try {
                                Api.send<Ok>("pantry/items/$id", "DELETE")
                                ready = false
                                onChanged()
                                store.loadGrocery()
                                dismiss()
                            } catch (e: Throwable) {
                                error = Api.message(e)
                            }
                        }
                    },
                    contentAlignment = Alignment.CenterStart,
                ) { Text("Delete item", style = Theme.body, color = Theme.destructive) }
            }
        }
    }
}

@Composable
private fun FormSwitch(label: String, checked: Boolean, onChange: (Boolean) -> Unit) {
    Row(Modifier.fillMaxWidth().heightIn(min = 44.dp).clickable { onChange(!checked) }, verticalAlignment = Alignment.CenterVertically) {
        Text(label, style = Theme.body, color = Theme.ink, modifier = Modifier.weight(1f))
        ThemeSwitch(checked, onChange)
    }
}
