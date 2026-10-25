package build.computerscience.dinnerdesk.ui

import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.outlined.ManageSearch
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.MoreHoriz
import androidx.compose.material.icons.outlined.CheckCircleOutline
import androidx.compose.material.icons.outlined.IosShare
import androidx.compose.material.icons.outlined.Numbers
import androidx.compose.material.icons.outlined.Restaurant
import androidx.compose.material.icons.outlined.ShoppingCart
import androidx.compose.material.icons.outlined.Storefront
import androidx.compose.material.icons.outlined.UnfoldMore
import androidx.compose.material.icons.outlined.Visibility
import androidx.compose.material.icons.outlined.VisibilityOff
import androidx.compose.material.icons.automirrored.outlined.Undo
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
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextDecoration
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import build.computerscience.dinnerdesk.data.Copy
import build.computerscience.dinnerdesk.data.GroceryLine
import build.computerscience.dinnerdesk.data.UsedMeal
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

@OptIn(ExperimentalFoundationApi::class)
@Composable
fun GroceryView() {
    val store = LocalStore.current
    val nav = LocalNav.current
    val context = LocalContext.current
    var storeFilter by rememberSaveable { mutableStateOf("") }
    var adding by remember { mutableStateOf(false) }
    var menu by remember { mutableStateOf(false) }
    var menuStatus by remember { mutableStateOf<String?>(null) }

    LaunchedEffect(Unit) { store.loadGrocery(onlyIfStale = true) }

    val allComplete = store.grocery.isNotEmpty() && store.grocery.all { it.checked || it.neverShop }
    val storeLines = if (storeFilter.isEmpty()) store.grocery else store.grocery.filter { it.store == storeFilter }
    val visible = storeLines.filter { !(store.hideChecked && (it.checked || it.neverShop)) }
    val completedCount = storeLines.count { it.checked || it.neverShop }
    val filterName = store.stores.firstOrNull { it.id == storeFilter }?.name

    // Sections follow the household's walk-the-store order.
    val blocks = buildList {
        for (aisle in store.aisles) add(Triple(aisle.id, if (store.showAisleNums) store.aisleTitle(aisle.id) else aisle.name, visible.filter { it.aisle == aisle.id }))
        val extra = visible.filter { line -> store.aisles.none { it.id == line.aisle } }
        if (extra.isNotEmpty()) add(Triple("extra", "Other", extra))
    }.filter { it.third.isNotEmpty() }

    fun persist() = store.launch { persistGroceryPrefs() }

    /** What's left to buy, grouped by aisle in walk-the-store order, for the selected store. */
    fun shareText(): String {
        val left = storeLines.filter { !it.checked && !it.neverShop }
        val title = filterName?.let { "Grocery list — $it" } ?: "Grocery list"
        if (left.isEmpty()) return "$title\n\nNothing left to buy."
        val groups = store.aisles.map { aisle -> aisle.name to left.filter { it.aisle == aisle.id } } +
            ("Other" to left.filter { line -> store.aisles.none { it.id == line.aisle } })
        val body = groups.filter { it.second.isNotEmpty() }.joinToString("\n\n") { (name, rows) ->
            (listOf(name.uppercase()) + rows.map { line -> "• " + listOf(line.quantity, line.name).filter { it.isNotEmpty() }.joinToString(" ") }).joinToString("\n")
        }
        return "$title\n\n$body"
    }

    Box(Modifier.fillMaxSize().background(Theme.bg)) {
        Column(Modifier.fillMaxSize()) {
            Row(Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 12.dp), verticalAlignment = Alignment.CenterVertically) {
                Text("Grocery", style = Theme.bigTitle, color = Theme.ink, modifier = Modifier.weight(1f))
                IconAction(Icons.Outlined.IosShare, "Share list") { shareText(context, shareText()) }
                IconAction(Icons.Filled.MoreHoriz, "Grocery List Settings") { menuStatus = null; menu = true }
            }
            RefreshBox({ store.loadGrocery(rebuild = true) }) {
                LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(bottom = 72.dp)) {
                    store.error?.let { err -> item { Box(Modifier.padding(horizontal = 16.dp, vertical = 4.dp)) { ErrorBanner(err) } } }
                    if (store.stores.isNotEmpty()) item {
                        Row(Modifier.horizontalScroll(rememberScrollState()).padding(horizontal = 16.dp, vertical = 8.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            Chip("All", storeFilter.isEmpty()) { storeFilter = "" }
                            for (shop in store.stores) Chip(shop.name, storeFilter == shop.id) { storeFilter = if (storeFilter == shop.id) "" else shop.id }
                        }
                    }
                    if (store.grocery.isEmpty()) {
                        item { EmptyState("List is empty", "Choose meals to build your grocery list.", Icons.Outlined.ShoppingCart) }
                        if (store.plan?.slots?.isEmpty() != false) item {
                            Box(Modifier.fillMaxWidth(), contentAlignment = Alignment.Center) { CreateMealPlanButton { store.launch { openSuggestions() } } }
                        }
                    } else {
                        if (blocks.isEmpty()) item {
                            val message = if (storeLines.isEmpty()) filterName?.let { "Nothing on the list for $it." } ?: "Nothing on the list."
                            else filterName?.let { "Everything for $it is checked off." } ?: "Everything is checked off."
                            Text(message, style = Theme.subtitle, color = Theme.muted, textAlign = TextAlign.Center, modifier = Modifier.fillMaxWidth().padding(vertical = 24.dp))
                        }
                        for ((id, name, rows) in blocks) {
                            stickyHeader(key = "h-$id") {
                                Box(Modifier.fillMaxWidth().background(Theme.bg).padding(start = 20.dp, end = 20.dp, top = 12.dp, bottom = 4.dp)) { ThemeHeader(name) }
                            }
                            items(rows, key = { it.id }) { line ->
                                GroceryRow(line) { nav.push(Route.GroceryItem(line.id)) }
                                Hairline(start = 60.dp)
                            }
                        }
                        if (completedCount > 0) item {
                            // Same switch as ⋯ → Show completed items, one tap from the list.
                            Row(
                                Modifier.fillMaxWidth().heightIn(min = 44.dp).clickable { store.hideChecked = !store.hideChecked; persist() },
                                horizontalArrangement = Arrangement.spacedBy(8.dp, Alignment.CenterHorizontally), verticalAlignment = Alignment.CenterVertically,
                            ) {
                                Icon(if (store.hideChecked) Icons.Outlined.Visibility else Icons.Outlined.VisibilityOff, null, tint = Theme.accent, modifier = Modifier.size(20.dp))
                                Text(if (store.hideChecked) "Show $completedCount completed" else "Hide completed", style = Theme.action, color = Theme.accent)
                            }
                        }
                    }
                }
            }
        }
        Box(
            Modifier.align(Alignment.BottomEnd).padding(end = 20.dp, bottom = 16.dp).size(60.dp)
                .shadow(10.dp, CircleShape, spotColor = Theme.ink.copy(alpha = 0.2f)).background(Theme.accent, CircleShape)
                .clickable { adding = true }.semantics { contentDescription = "Add item" },
            contentAlignment = Alignment.Center,
        ) { Icon(Icons.Filled.Add, null, tint = Color.White, modifier = Modifier.size(28.dp)) }
    }

    if (menu) {
        MenuSheet(onDismiss = { menu = false }, items = listOf(
            MenuItem("Show completed items", Icons.Outlined.Visibility, dismissOnSelection = false, isOn = !store.hideChecked) {
                store.hideChecked = !store.hideChecked; persist()
            },
            MenuItem(
                if (allComplete) "Uncheck all" else "Complete all", if (allComplete) Icons.AutoMirrored.Outlined.Undo else Icons.Outlined.CheckCircleOutline,
                dismissOnSelection = false, status = menuStatus,
            ) {
                val uncheck = allComplete
                store.launch {
                    if (uncheck) uncheckAllGrocery() else markAllGroceryComplete()
                    if (error == null) menuStatus = if (uncheck) "Unchecked" else "Completed"
                }
            },
            MenuItem("Show meals under each item", Icons.Outlined.Restaurant, dismissOnSelection = false, isOn = store.showMeals) {
                store.showMeals = !store.showMeals; persist()
            },
            MenuItem("Show aisle numbers", Icons.Outlined.Numbers, dismissOnSelection = false, isOn = store.showAisleNums) {
                store.showAisleNums = !store.showAisleNums; persist()
            },
            MenuItem("Edit stores & aisles", Icons.Outlined.Storefront) { nav.push(Route.GroceryStores) },
        ))
    }
    if (adding) Sheet(onDismiss = { adding = false }) { AddGrocerySheet(storeFilter.ifEmpty { null }) }
}

@Composable
private fun GroceryRow(line: GroceryLine, onOpen: () -> Unit) {
    val store = LocalStore.current
    val large = isAccessibilitySize
    val note = if (store.showMeals && line.usedBy.isNotEmpty()) line.usedBy.map(::shortMealName).filter { it.isNotEmpty() }.joinToString(" · ") else ""
    Row(Modifier.fillMaxWidth().background(Theme.bg).heightIn(min = 56.dp)) {
        Box(
            Modifier.width(60.dp).heightIn(min = 56.dp).clickable { store.launch { toggleGrocery(line) } }
                .semantics { contentDescription = if (line.checked) "Uncheck ${line.name}" else "Check off ${line.name}" },
            contentAlignment = Alignment.Center,
        ) { CheckCircle(line.checked, 26.dp) }
        Row(
            Modifier.weight(1f).heightIn(min = 56.dp).clickable(onClick = onOpen).padding(end = 16.dp, top = 8.dp, bottom = 8.dp),
            verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            if (line.ingredientPhotoPath != null) RecipePhoto(line.ingredientPhotoPath)
            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(2.dp)) {
                Text(
                    line.name, style = Theme.body.copy(textDecoration = if (line.checked) TextDecoration.LineThrough else null),
                    color = if (line.checked) Theme.muted else Theme.ink,
                )
                // Large text: the amount goes under the name so the name keeps the width.
                if (large && line.quantity.isNotEmpty()) Text(line.quantity, style = Theme.count, color = Theme.muted)
                if (note.isNotEmpty()) Text(note, style = Theme.subtitle, color = Theme.muted)
                if (line.fromPantry && !line.neverShop) Text(Copy.text("grocery.pantry"), style = Theme.subtitle, color = Theme.muted)
            }
            if (!large && line.quantity.isNotEmpty()) Text(line.quantity, style = Theme.count, color = Theme.muted)
        }
    }
}

private fun shortMealName(name: String): String {
    val raw = name.trim()
    if (raw.isEmpty()) return ""
    val head = raw.split(",", limit = 2)[0].trim()
    val i = head.indexOf(" with ", ignoreCase = true)
    return if (i >= 0) head.substring(0, i).trim() else head
}

@Composable
fun GroceryItemView(lineId: Int) {
    val store = LocalStore.current
    val nav = LocalNav.current
    val dismiss = LocalDismiss.current
    val scope = rememberCoroutineScope()
    var editing by remember { mutableStateOf(false) }
    var subName by remember { mutableStateOf("") }
    var suggestions by remember { mutableStateOf<List<String>>(emptyList()) }
    var suggestJob by remember { mutableStateOf<Job?>(null) }
    /** After a substitution the list is rebuilt and the item comes back as a new line. This follows it. */
    var followId by remember { mutableStateOf<Int?>(null) }
    val line = store.grocery.firstOrNull { it.id == (followId ?: lineId) }

    Column(Modifier.fillMaxSize().background(Theme.bg)) {
        NavBar(actions = { if (line != null) LinkButton("Edit") { editing = true } })
        if (line == null) {
            EmptyState("Item gone", "", Icons.Outlined.ShoppingCart)
            return@Column
        }
        Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                Text(listOf(line.quantity.trim(), line.name.trim()).filter { it.isNotEmpty() }.joinToString(" "), style = Theme.title, color = Theme.ink, maxLines = 2, overflow = TextOverflow.Ellipsis)
                Text(store.aisleName(line.aisle).uppercase(), style = Theme.subtitle, color = Theme.muted)
            }
            RecipePhoto(line.ingredientPhotoPath, large = true, hideUnavailable = true)
            val field: @Composable (Modifier) -> Unit = { m ->
                TextBox(subName, { q ->
                    subName = q
                    suggestJob?.cancel()
                    suggestJob = scope.launch { delay(220); suggestions = store.suggestGroceryItems(q) }
                }, "Try another item", modifier = m, corner = 8.dp)
            }
            if (isAccessibilitySize) {
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) { Text("Substitute", style = Theme.mealName, color = Theme.ink); field(Modifier) }
            } else {
                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                    Text("Substitute", style = Theme.mealName, color = Theme.ink, maxLines = 1)
                    field(Modifier.weight(1f))
                }
            }
            for (name in suggestions) {
                Text(name, style = Theme.body, color = Theme.ink, modifier = Modifier.fillMaxWidth().clickable { subName = name; suggestions = emptyList() }.padding(vertical = 6.dp))
            }
            if (subName.isNotBlank()) {
                LinkButton("Use this instead", style = Theme.body) {
                    val target = subName.trim().lowercase()
                    val current = line.id
                    scope.launch {
                        store.addSubstitute(line.name, subName)
                        if (store.grocery.any { it.id == current }) return@launch
                        val next = store.grocery.firstOrNull { it.name.lowercase() == target }
                        if (next != null) {
                            followId = next.id
                            subName = ""
                            suggestions = emptyList()
                        } else dismiss()
                    }
                }
            }
            Text("You'll use this in…", style = Theme.subtitle, color = Theme.ink, modifier = Modifier.semantics { heading() })
            when {
                line.usedIn.isNotEmpty() -> for (meal in line.usedIn) {
                    val rid = meal.recipeId
                    Box(if (rid != null) Modifier.clickable { nav.push(Route.Recipe(rid)) } else Modifier) { MealLabel(meal) }
                }
                line.usedBy.isNotEmpty() -> for (name in line.usedBy) Text(name, style = Theme.body, color = Theme.ink)
                else -> Text("Added by you", style = Theme.body, color = Theme.muted)
            }
            Column {
                PickerRow("Store", store.storeName(line), store.stores.map { it.id to it.name }) { id -> store.launch { setGroceryStore(line, id) } }
                Hairline()
                PickerRow("Aisle", store.aisleName(line.aisle), store.aisles.map { it.id to it.name }) { id -> store.launch { setGroceryAisle(line, id) } }
                Hairline()
                ToggleLine("In my pantry", line.fromPantry) { next -> store.launch { setPantryFlags(line.name, next, line.neverShop) } }
                Hairline()
                ToggleLine("Always check off", line.neverShop) { next -> store.launch { setPantryFlags(line.name, line.fromPantry, next) } }
            }
        }
    }
    if (editing && line != null) Sheet(onDismiss = { editing = false }, full = false) { EditGrocerySheet(line) }
}

@Composable
private fun ToggleLine(label: String, checked: Boolean, onChange: (Boolean) -> Unit) {
    Row(Modifier.fillMaxWidth().heightIn(min = 44.dp).clickable { onChange(!checked) }, verticalAlignment = Alignment.CenterVertically) {
        Text(label, style = Theme.rowTitle, color = Theme.ink, modifier = Modifier.weight(1f))
        ThemeSwitch(checked, onChange)
    }
}

@Composable
private fun MealLabel(meal: UsedMeal) {
    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
        RecipePhoto(meal.photoPath)
        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Text(meal.name, style = Theme.mealName, color = Theme.ink, maxLines = 2, overflow = TextOverflow.Ellipsis)
            if (meal.quantity.isNotEmpty()) Text(meal.quantity, style = Theme.count, color = Theme.muted)
        }
    }
}

/** Label, then the current value with a menu of choices (SwiftUI `Menu`). */
@Composable
fun PickerRow(label: String, value: String, options: List<Pair<String, String>>, onPick: (String) -> Unit) {
    var open by remember { mutableStateOf(false) }
    Row(Modifier.fillMaxWidth().heightIn(min = 44.dp), verticalAlignment = Alignment.CenterVertically) {
        Text(label, style = Theme.rowTitle, color = Theme.ink, modifier = Modifier.weight(1f))
        Box {
            Row(Modifier.clickable { open = true }.padding(vertical = 8.dp), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                Text(value, style = Theme.body, color = Theme.muted)
                Icon(Icons.Outlined.UnfoldMore, null, tint = Theme.muted, modifier = Modifier.size(16.dp))
            }
            DropdownMenu(open, { open = false }, containerColor = Theme.surface) {
                for ((id, name) in options) DropdownMenuItem({ Text(name, style = Theme.body) }, { open = false; onPick(id) })
            }
        }
    }
}

@Composable
private fun EditGrocerySheet(line: GroceryLine) {
    val store = LocalStore.current
    val dismiss = LocalDismiss.current
    val scope = rememberCoroutineScope()
    var qty by remember { mutableStateOf(line.quantity) }
    var itemName by remember { mutableStateOf(line.name) }
    Column(Modifier.fillMaxWidth().background(Theme.bg).padding(bottom = 24.dp)) {
        SheetBar("Edit item", confirm = "Save", confirmEnabled = itemName.isNotBlank(), onConfirm = {
            scope.launch {
                val name = itemName.trim()
                if (name.isNotEmpty() && name != line.name) store.patchGrocery(line, mapOf("custom_text" to name))
                val trimmed = qty.trim()
                if (trimmed != line.quantity) store.setGroceryQuantity(line, trimmed)
                if (store.error == null) dismiss()
            }
        })
        FormSection {
            FormField(qty, { qty = it }, "Amount")
            Hairline()
            FormField(itemName, { itemName = it }, "Item name")
        }
    }
}

@Composable
private fun AddGrocerySheet(storeId: String?) {
    val store = LocalStore.current
    val dismiss = LocalDismiss.current
    val scope = rememberCoroutineScope()
    var newName by remember { mutableStateOf("") }
    var newQty by remember { mutableStateOf("") }
    /** The single best match for what's typed. */
    var suggestion by remember { mutableStateOf<String?>(null) }
    var suggestJob by remember { mutableStateOf<Job?>(null) }
    var saving by remember { mutableStateOf(false) }
    val canAdd = !saving && newName.isNotBlank()

    fun add() {
        saving = true
        scope.launch {
            store.addGroceryLine(newName, newQty, storeId)
            saving = false
            if (store.error == null) dismiss()
        }
    }

    Column(Modifier.fillMaxSize().background(Theme.bg)) {
        SheetBar("Add item", confirm = "Add", confirmEnabled = canAdd, onConfirm = ::add)
        FormSection {
            FormField(newName, { q ->
                newName = q
                suggestJob?.cancel()
                suggestJob = scope.launch {
                    delay(220)
                    val best = store.suggestGroceryItems(q).firstOrNull()
                    suggestion = if (best?.lowercase() == q.trim().lowercase()) null else best
                }
            }, "Item")
            suggestion?.let { s ->
                Hairline()
                Row(
                    Modifier.fillMaxWidth().heightIn(min = 44.dp).clickable { newName = s; suggestion = null }.semantics { contentDescription = "Use suggestion: $s" },
                    verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    Icon(Icons.AutoMirrored.Outlined.ManageSearch, null, tint = Theme.muted, modifier = Modifier.size(20.dp))
                    Text(s, style = Theme.body, color = Theme.accent)
                }
            }
            Hairline()
            FormField(newQty, { newQty = it }, "Quantity (optional)", keyboard = KeyboardOptions.Default, actions = KeyboardActions(onDone = { if (canAdd) add() }))
            Hairline()
            Box(Modifier.fillMaxWidth().heightIn(min = 44.dp).clickable(enabled = canAdd) { add() }, contentAlignment = Alignment.CenterStart) {
                Text("Add to list", style = Theme.body, color = if (canAdd) Theme.accent else Theme.muted.copy(alpha = 0.5f))
            }
        }
        Spacer(Modifier.height(8.dp))
    }
}
