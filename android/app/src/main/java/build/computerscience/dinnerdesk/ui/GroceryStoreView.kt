package build.computerscience.dinnerdesk.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.gestures.detectDragGestures
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.FormatListNumbered
import androidx.compose.material.icons.filled.DragHandle
import androidx.compose.material.icons.filled.KeyboardArrowDown
import androidx.compose.material.icons.filled.Search
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.key
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.layout.onSizeChanged
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.zIndex
import build.computerscience.dinnerdesk.data.Api
import build.computerscience.dinnerdesk.data.ItemPlacement
import build.computerscience.dinnerdesk.data.KitchenApi
import build.computerscience.dinnerdesk.data.KitchenDefaults
import build.computerscience.dinnerdesk.data.ShopAisle
import build.computerscience.dinnerdesk.data.ShopStore
import kotlinx.coroutines.async
import kotlinx.coroutines.launch

private enum class PlacementTab { Unset, All }

/** Your stores, the aisle order, and which store/aisle each item belongs to. */
@Composable
fun GroceryStoreView() {
    val store = LocalStore.current
    val nav = LocalNav.current
    val scope = rememberCoroutineScope()
    var stores by remember { mutableStateOf(ShopStore.defaults) }
    var aisles by remember { mutableStateOf(ShopAisle.defaults) }
    var items by remember { mutableStateOf<List<ItemPlacement>>(emptyList()) }
    var tab by remember { mutableStateOf(PlacementTab.Unset) }
    var query by remember { mutableStateOf("") }
    var newStore by remember { mutableStateOf("") }
    var addingStore by remember { mutableStateOf(false) }
    var doomedStore by remember { mutableStateOf<ShopStore?>(null) }
    var error by remember { mutableStateOf<String?>(null) }

    suspend fun load() {
        try {
            kotlinx.coroutines.coroutineScope {
                val itemsBox = async { KitchenApi.placements() }
                val prefs = KitchenApi.prefs()
                stores = KitchenDefaults.stores(prefs)
                aisles = KitchenDefaults.aisles(prefs)
                items = itemsBox.await()
            }
            error = null
        } catch (e: Throwable) {
            if (!Api.isCancellation(e)) error = Api.message(e)
        }
    }

    suspend fun saveStores(next: List<ShopStore>) {
        val before = stores
        stores = next
        try {
            KitchenApi.saveGroceryPrefs(mapOf("stores" to KitchenDefaults.storesJson(next)))
            val valid = next.map { it.id }.toSet()
            items = items.map { if (it.store !in valid) it.copy(store = "") else it }
            store.loadGrocery()
        } catch (e: Throwable) {
            stores = before
            error = Api.message(e)
        }
    }

    fun place(item: ItemPlacement, storeId: String?, aisleId: String?) {
        val before = items.firstOrNull { it.id == item.id } ?: return
        items = items.map { if (it.id == item.id) it.copy(store = storeId ?: it.store, aisle = aisleId ?: it.aisle) else it }
        scope.launch {
            try {
                KitchenApi.setPlacement(before, storeId, aisleId)
                store.loadGrocery()
            } catch (e: Throwable) {
                items = items.map { if (it.id == item.id) before else it }
                error = Api.message(e)
            }
        }
    }

    LaunchedEffect(Unit) { load() }

    val unset = items.filter { it.store.isEmpty() }
    val q = query.trim().lowercase()
    val shown = (if (tab == PlacementTab.Unset) unset else items).let { base -> if (q.isEmpty()) base else base.filter { it.name.lowercase().contains(q) } }
    val known = aisles.map { it.id }.toSet()
    val groups = buildList {
        for (aisle in aisles) add(aisle.name to shown.filter { it.aisle == aisle.id })
        val extra = shown.filter { it.aisle !in known }
        if (extra.isNotEmpty()) add("Other" to extra)
    }.filter { it.second.isNotEmpty() }

    Column(Modifier.fillMaxSize().background(Theme.bg)) {
        NavBar("Stores & aisles")
        TextBox(
            query, { query = it }, "Search items", modifier = Modifier.padding(horizontal = 16.dp, vertical = 6.dp), corner = 10.dp,
            background = Color(0x1F767680), border = Color.Transparent,
            leading = { Icon(Icons.Filled.Search, null, tint = Theme.muted, modifier = Modifier.size(18.dp)) },
        )
        ThemeList({ load() }) {
            error?.let { Box(Modifier.padding(16.dp)) { ErrorBanner(it) } }
            ListHeader("Your stores")
            Box(Modifier.padding(horizontal = 20.dp, vertical = 8.dp)) {
                Flow(8.dp) {
                    for (shop in stores) key(shop.id) {
                        // A menu per chip, with the store's remove option.
                        var open by remember { mutableStateOf(false) }
                        Box {
                            KitchenChip(shop.name, items.count { it.store == shop.id }, selected = false) { open = true }
                            DropdownMenu(open, { open = false }, containerColor = Theme.surface) {
                                DropdownMenuItem({ Text("Remove ${shop.name}", style = Theme.body, color = Theme.destructive) }, { open = false; doomedStore = shop })
                            }
                        }
                    }
                    KitchenChip("+ Add store", null, selected = false, dashed = true) { addingStore = true }
                }
            }
            Box(Modifier.padding(horizontal = 20.dp, vertical = 4.dp)) { StarTip("kitchen.store-chips") }
            ListRow(onClick = { nav.push(Route.AisleOrder) }) {
                ThemeIconRow("Aisle order", Icons.Outlined.FormatListNumbered, "${aisles.size} aisles")
            }
            ListHeader("Store & aisle for each item")
            Box(Modifier.padding(horizontal = 20.dp, vertical = 6.dp)) {
                Segmented(listOf(PlacementTab.Unset to "Not set · ${unset.size}", PlacementTab.All to "All items · ${items.size}"), tab) { tab = it }
            }
            Box(Modifier.padding(horizontal = 20.dp, vertical = 6.dp)) { StarTip("kitchen.store-per-item") }
            if (groups.isEmpty()) {
                Text(
                    if (tab == PlacementTab.Unset) "Every item has a store." else "Items show up here once they're on a grocery list or in your pantry.",
                    style = Theme.body, color = Theme.muted, modifier = Modifier.padding(20.dp),
                )
            }
            for ((name, rows) in groups) {
                ListHeader(name)
                for (item in rows) {
                    ListRow(chevron = false) { PlacementRow(item, stores, aisles) { s, a -> place(item, s, a) } }
                }
            }
        }
    }

    if (addingStore) {
        TextFieldAlert("Add a store", newStore, { newStore = it }, "Store name", "Add", onConfirm = {
            val name = newStore.trim()
            newStore = ""
            if (name.isNotEmpty()) {
                try {
                    val id = KitchenDefaults.slug(name)
                    if (stores.none { it.id == id }) scope.launch { saveStores(stores + ShopStore(id, name)) }
                } catch (e: Throwable) {
                    error = Api.message(e)
                }
            }
        }, onDismiss = { addingStore = false; newStore = "" })
    }
    doomedStore?.let { shop ->
        ConfirmDialog("Remove ${shop.name}?", "Remove", message = "You can add it back anytime.", onConfirm = {
            scope.launch { saveStores(stores.filter { it.id != shop.id }) }
        }, onDismiss = { doomedStore = null })
    }
}

/** One item on one line: name, then a store menu and an aisle menu. */
@Composable
private fun PlacementRow(item: ItemPlacement, stores: List<ShopStore>, aisles: List<ShopAisle>, onChange: (String?, String?) -> Unit) {
    val storeName = stores.firstOrNull { it.id == item.store }?.name ?: "Not set"
    val aisleName = aisles.firstOrNull { it.id == item.aisle }?.name ?: "Other"
    val pickers: @Composable () -> Unit = {
        Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
            MenuChip(storeName, unset = item.store.isEmpty(), label = "Store for ${item.name}: $storeName",
                options = listOf("" to "Not set") + stores.map { it.id to it.name }) { onChange(it, null) }
            MenuChip(aisleName, unset = false, label = "Aisle for ${item.name}: $aisleName", options = aisles.map { it.id to it.name }) { onChange(null, it) }
        }
    }
    if (isAccessibilitySize) {
        Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text(item.name, style = Theme.mealName, color = Theme.ink, maxLines = 2)
            pickers()
        }
    } else {
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Text(item.name, style = Theme.mealName, color = Theme.ink, maxLines = 2, modifier = Modifier.weight(1f))
            pickers()
        }
    }
}

@Composable
private fun MenuChip(text: String, unset: Boolean, label: String, options: List<Pair<String, String>>, onPick: (String) -> Unit) {
    var open by remember { mutableStateOf(false) }
    Box {
        Row(
            Modifier.heightIn(min = 34.dp).clip(CircleShape).background(if (unset) Color.Transparent else Theme.chip)
                .then(if (unset) Modifier.dashedBorder(Theme.line, 17.dp) else Modifier)
                .clickable { open = true }.semantics { contentDescription = label }.padding(horizontal = 12.dp),
            verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(4.dp),
        ) {
            Text(text, style = Theme.chipLabel, color = if (unset) Theme.muted else Theme.ink, maxLines = 1)
            Icon(Icons.Filled.KeyboardArrowDown, null, tint = if (unset) Theme.muted else Theme.ink, modifier = Modifier.size(16.dp))
        }
        DropdownMenu(open, { open = false }, containerColor = Theme.surface) {
            for ((id, name) in options) DropdownMenuItem({ Text(name, style = Theme.body) }, { open = false; onPick(id) })
        }
    }
}

/** Put aisles in the order you walk the store; give them numbers. Drag the handle to reorder. */
@Composable
fun AisleOrderView() {
    val store = LocalStore.current
    val scope = rememberCoroutineScope()
    var aisles by remember { mutableStateOf(ShopAisle.defaults) }
    var counts by remember { mutableStateOf<Map<String, Int>>(emptyMap()) }
    var newAisle by remember { mutableStateOf("") }
    var addingAisle by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    var dragging by remember { mutableStateOf<String?>(null) }
    var dragOffset by remember { mutableFloatStateOf(0f) }
    var rowHeight by remember { mutableIntStateOf(1) }

    suspend fun save(next: List<ShopAisle>) {
        aisles = next
        try {
            KitchenApi.saveGroceryPrefs(mapOf("aisles" to KitchenDefaults.aislesJson(next)))
            store.loadGrocery()
        } catch (e: Throwable) {
            error = Api.message(e)
        }
    }

    LaunchedEffect(Unit) {
        try {
            aisles = KitchenDefaults.aisles(KitchenApi.prefs())
            error = null
        } catch (e: Throwable) {
            if (!Api.isCancellation(e)) error = Api.message(e)
        }
        try {
            counts = KitchenApi.placements().groupingBy { it.aisle }.eachCount()
        } catch (e: Throwable) {
            if (!Api.isCancellation(e)) error = Api.message(e)
        }
    }
    val latest by rememberUpdatedState(aisles)
    DisposableCleanup { store.launch { KitchenApi.saveGroceryPrefs(mapOf("aisles" to KitchenDefaults.aislesJson(latest))); loadGrocery() } }

    Column(Modifier.fillMaxSize().background(Theme.bg)) {
        NavBar("Aisle order")
        ThemeList {
            error?.let { Box(Modifier.padding(16.dp)) { ErrorBanner(it) } }
            ListHeader("Walk-the-store order")
            for (aisle in aisles) key(aisle.id) {
                val isDragged = dragging == aisle.id
                Box(
                    Modifier.zIndex(if (isDragged) 1f else 0f).graphicsLayer {
                        translationY = if (isDragged) dragOffset else 0f
                        shadowElevation = if (isDragged) 8f else 0f
                    }.onSizeChanged { rowHeight = maxOf(1, it.height) },
                ) {
                    ListRow(chevron = false) {
                        Row(Modifier.weight(1f), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                            BasicTextField(
                                aisle.number, { value -> aisles = aisles.map { if (it.id == aisle.id) it.copy(number = value.filter(Char::isDigit)) else it } },
                                textStyle = Theme.count.copy(color = Theme.ink, textAlign = TextAlign.Center), singleLine = true,
                                cursorBrush = SolidColor(Theme.accent),
                                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number, imeAction = ImeAction.Done),
                                keyboardActions = KeyboardActions(onDone = { scope.launch { save(aisles) } }),
                                modifier = Modifier.width(44.dp).clip(RoundedCornerShape(8.dp)).background(Theme.chip).padding(vertical = 7.dp)
                                    .semantics { contentDescription = "Aisle number for ${aisle.name}" },
                                decorationBox = { inner -> Box(contentAlignment = Alignment.Center) { if (aisle.number.isEmpty()) Text("#", style = Theme.count, color = Theme.muted); inner() } },
                            )
                            Text(aisle.name, style = Theme.mealName, color = Theme.ink, maxLines = 2, modifier = Modifier.weight(1f))
                            val n = counts[aisle.id] ?: 0
                            Text(if (n == 1) "1 item" else "$n items", style = Theme.subtitle, color = Theme.muted)
                        }
                        Box(
                            Modifier.size(44.dp).semantics { contentDescription = "Reorder ${aisle.name}" }.pointerInput(aisle.id) {
                                detectDragGestures(
                                    onDragStart = { dragging = aisle.id; dragOffset = 0f },
                                    onDragEnd = { dragging = null; dragOffset = 0f; scope.launch { save(aisles) } },
                                    onDragCancel = { dragging = null; dragOffset = 0f },
                                ) { change, amount ->
                                    change.consume()
                                    dragOffset += amount.y
                                    val list = aisles.toMutableList()
                                    val i = list.indexOfFirst { it.id == aisle.id }
                                    if (dragOffset > rowHeight / 2f && i < list.lastIndex) {
                                        list.add(i + 1, list.removeAt(i)); aisles = list; dragOffset -= rowHeight
                                    } else if (dragOffset < -rowHeight / 2f && i > 0) {
                                        list.add(i - 1, list.removeAt(i)); aisles = list; dragOffset += rowHeight
                                    }
                                }
                            },
                            contentAlignment = Alignment.Center,
                        ) { Icon(Icons.Filled.DragHandle, null, tint = Theme.muted) }
                    }
                }
            }
            ThemeAddRow("Add aisle") { addingAisle = true }
            Box(Modifier.padding(horizontal = 20.dp, vertical = 8.dp)) { StarTip("kitchen.aisle-order") }
        }
    }
    if (addingAisle) {
        TextFieldAlert("Add an aisle", newAisle, { newAisle = it }, "Aisle name", "Add", onConfirm = {
            val name = newAisle.trim()
            newAisle = ""
            if (name.isNotEmpty()) {
                try {
                    val id = KitchenDefaults.slug(name)
                    if (aisles.none { it.id == id }) {
                        val next = aisles.filter { it.id != "other" } + ShopAisle(id, name) + aisles.filter { it.id == "other" }
                        scope.launch { save(next) }
                    }
                } catch (e: Throwable) {
                    error = Api.message(e)
                }
            }
        }, onDismiss = { addingAisle = false; newAisle = "" })
    }
}
