package build.computerscience.dinnerdesk.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.CheckBox
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.MoreHoriz
import androidx.compose.material.icons.filled.Remove
import androidx.compose.material.icons.filled.Sync
import androidx.compose.material.icons.outlined.AddCircleOutline
import androidx.compose.material.icons.outlined.CalendarToday
import androidx.compose.material.icons.outlined.CheckBoxOutlineBlank
import androidx.compose.material.icons.outlined.CheckCircleOutline
import androidx.compose.material.icons.outlined.Delete
import androidx.compose.material.icons.outlined.Edit
import androidx.compose.material.icons.outlined.Flag
import androidx.compose.material.icons.outlined.Gesture
import androidx.compose.material.icons.outlined.GridView
import androidx.compose.material.icons.outlined.Inbox
import androidx.compose.material.icons.outlined.RadioButtonUnchecked
import androidx.compose.material.icons.outlined.SaveAlt
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.DatePicker
import androidx.compose.material3.DatePickerDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.SelectableDates
import androidx.compose.material3.Text
import androidx.compose.material3.rememberDatePickerState
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
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import build.computerscience.dinnerdesk.data.Api
import build.computerscience.dinnerdesk.data.Plan
import build.computerscience.dinnerdesk.data.PlanList
import build.computerscience.dinnerdesk.data.PlanSlot
import build.computerscience.dinnerdesk.data.SavedPlan
import build.computerscience.dinnerdesk.data.SwapOption
import build.computerscience.dinnerdesk.data.SwapOptions
import build.computerscience.dinnerdesk.data.Ok
import build.computerscience.dinnerdesk.data.dayTitle
import build.computerscience.dinnerdesk.data.planDate
import build.computerscience.dinnerdesk.data.shortDate
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import java.time.Instant
import java.time.LocalDate
import java.time.OffsetDateTime
import java.time.ZoneId
import java.time.ZoneOffset
import java.time.format.DateTimeFormatter
import java.util.Locale

@Composable
fun PlanView() {
    val store = LocalStore.current
    val nav = LocalNav.current
    val selectTab = LocalSelectTab.current
    var grid by rememberSaveable { mutableStateOf(false) }
    var editing by rememberSaveable { mutableStateOf(false) }
    var selected by remember { mutableStateOf(setOf<Int>()) }
    var menu by remember { mutableStateOf(false) }
    var picking by remember { mutableStateOf<PlanSlot?>(null) }
    var drafts by remember { mutableStateOf(false) }
    var savingDraft by remember { mutableStateOf(false) }
    var draftTitle by remember { mutableStateOf("") }
    var removing by remember { mutableStateOf(false) }
    val large = isAccessibilitySize

    fun setEditing(on: Boolean) {
        editing = on
        if (!on) selected = emptySet()
    }

    RefreshBox({ store.loadAll() }) {
        Column(
            Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Row(Modifier.fillMaxWidth().padding(bottom = 4.dp), verticalAlignment = Alignment.CenterVertically) {
                Text(store.plan?.title ?: "This week", style = Theme.bigTitle, color = Theme.ink, modifier = Modifier.weight(1f))
                // While editing, a visible Done is the way out; the ⋯ menu alone was too hidden.
                if (editing) LinkButton("Done") { setEditing(false) }
                IconAction(Icons.Filled.MoreHoriz, "Plan menu") { menu = true }
            }
            store.error?.let { error ->
                ErrorBanner(error)
                if (error.contains("filter", ignoreCase = true)) {
                    LinkButton("Adjust filters") { nav.push(Route.Filters) }
                    LinkButton("Choose meals") { store.error = null; selectTab(AppTab.Recipes) }
                }
            }
            val plan = store.plan
            if (plan == null) {
                Spinner()
            } else {
                val note = plan.suggestionNote
                if (plan.status == "suggested" && !note.isNullOrEmpty()) {
                    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        Text(note, style = Theme.subtitle, color = Theme.muted)
                        Text("Improve your results", style = Theme.subtitle, color = Theme.accent, modifier = Modifier.clickable { nav.push(Route.TasteLab(swipe = true)) })
                    }
                }
                if (plan.slots.isEmpty()) {
                    Column(Modifier.fillMaxWidth(), horizontalAlignment = Alignment.CenterHorizontally) {
                        EmptyState("Nothing on this plan", "Get suggestions for your next meals.", Icons.Outlined.CalendarToday)
                        CreateMealPlanButton { store.launch { openSuggestions() } }
                        AddMealsButton { selectTab(AppTab.Recipes) }
                    }
                }
                if (editing && plan.slots.isNotEmpty()) {
                    val all = selected.size == plan.slots.size
                    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                        Text(
                            if (all) "Deselect all" else "Select all", style = Theme.body, color = Theme.ink,
                            modifier = Modifier.clickable { selected = if (all) emptySet() else plan.slots.map { it.id }.toSet() },
                        )
                        Spacer(Modifier.weight(1f))
                        Text("${selected.size} selected", style = Theme.body, color = Theme.muted)
                    }
                    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                        LinkButton("Mark cooked", enabled = selected.isNotEmpty(), style = Theme.body) {
                            val ids = selected
                            store.launch { markCooked(ids); selected = emptySet() }
                        }
                        Spacer(Modifier.weight(1f))
                        LinkButton("Remove", enabled = selected.isNotEmpty(), color = Theme.destructive, style = Theme.body) { removing = true }
                    }
                }
                for ((day, slots) in groups(plan)) {
                    if (day >= 0) ThemeHeader(dayTitle(plan.startDate, day))
                    if (grid && !editing && !large) {
                        for (pair in slots.chunked(2)) {
                            Row(horizontalArrangement = Arrangement.spacedBy(16.dp)) {
                                for (slot in pair) Box(Modifier.weight(1f)) {
                                    MealCard(slot, plan, grid = true, editing = false, selected = false, onSelect = {}, onSchedule = { picking = slot })
                                }
                                if (pair.size == 1) Spacer(Modifier.weight(1f))
                            }
                        }
                    } else {
                        for (slot in slots) {
                            MealCard(
                                slot, plan, grid = false, editing = editing, selected = slot.id in selected,
                                onSelect = { selected = if (slot.id in selected) selected - slot.id else selected + slot.id },
                                onSchedule = { picking = slot },
                            )
                            Hairline()
                        }
                    }
                }
                if (plan.slots.isNotEmpty()) AddMealsButton { selectTab(AppTab.Recipes) }
            }
        }
    }

    if (menu) {
        MenuSheet(onDismiss = { menu = false }, items = listOf(
            MenuItem(CREATE_MEAL_PLAN, Icons.Outlined.AddCircleOutline, createsMealPlan = true) { store.launch { openSuggestions() } },
            MenuItem("Fill in this plan", Icons.Outlined.AddCircleOutline) { store.launch { openSuggestions(keepCurrent = true) } },
            MenuItem(if (editing) "Finish editing" else "Edit plan", if (editing) Icons.Outlined.CheckCircleOutline else Icons.Outlined.Edit) { setEditing(!editing) },
            MenuItem("Mark all cooked", Icons.Outlined.CheckCircleOutline) { store.launch { markAllCooked() } },
            MenuItem(if (grid) "List View" else "Grid View", Icons.Outlined.GridView) { grid = !grid },
            MenuItem("Save as draft", Icons.Outlined.SaveAlt) { draftTitle = store.plan?.title ?: "Saved plan"; savingDraft = true },
            MenuItem("Saved plans & history", Icons.Outlined.Inbox) { drafts = true },
        ))
    }
    if (savingDraft) {
        TextFieldAlert("Save as draft", draftTitle, { draftTitle = it }, "Plan name", "Save",
            onConfirm = { val t = draftTitle; store.launch { saveDraft(t) } }, onDismiss = { savingDraft = false })
    }
    if (removing) {
        val count = selected.size
        RemovalConfirmation(
            title = "Remove $count ${if (count == 1) "meal" else "meals"}?",
            message = "Selected meals will be removed from your plan.",
            actionTitle = if (count == 1) "Remove meal" else "Remove meals",
            onDismiss = { removing = false },
        ) {
            store.removeSlots(selected)
            selected = emptySet()
        }
    }
    picking?.let { slot -> Sheet(onDismiss = { picking = null }, full = false) { ScheduleMealSheet(slot) } }
    if (drafts) {
        Sheet(onDismiss = { drafts = false }) {
            val sheetNav = remember { Nav(Route.PlanHome) }
            NavStack(sheetNav) { route -> if (route == Route.PlanHome) SavedPlansView() else RouteContent(route) }
        }
    }
}

@Composable
private fun AddMealsButton(onClick: () -> Unit) {
    Row(
        Modifier.heightIn(min = 44.dp).clip(RoundedCornerShape(8.dp)).clickable(onClick = onClick).padding(horizontal = 4.dp),
        verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp),
    ) {
        Icon(Icons.Filled.Add, null, tint = Theme.accent, modifier = Modifier.size(20.dp))
        Text("Add meals", style = Theme.action, color = Theme.accent)
    }
}

private fun groups(plan: Plan): List<Pair<Int, List<PlanSlot>>> =
    plan.slots.map { it.dayIndex ?: -1 }.toSortedSet().map { day ->
        day to plan.slots.filter { (it.dayIndex ?: -1) == day }.sortedWith(compareBy<PlanSlot> { it.cooked }.thenBy { it.id })
    }

private fun scheduleLabel(slot: PlanSlot, plan: Plan): String {
    val day = slot.dayIndex ?: return "Schedule"
    val start = planDate(plan.startDate) ?: return "Schedule"
    return shortDate(start.plusDays(day.toLong()))
}

/** One meal: a square photo with the cooked check, the name, then the schedule button or edit controls. */
@Composable
private fun MealCard(
    slot: PlanSlot, plan: Plan, grid: Boolean, editing: Boolean, selected: Boolean,
    onSelect: () -> Unit, onSchedule: () -> Unit,
) {
    val large = isAccessibilitySize
    Box(Modifier.fillMaxWidth().alpha(if (slot.cooked) 0.45f else 1f)) {
        when {
            grid -> Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                MealPhoto(slot, null, editing)
                MealTitle(slot, editing)
            }
            large -> Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                Row(verticalAlignment = Alignment.Top) {
                    MealPhoto(slot, 148, editing)
                    Spacer(Modifier.weight(1f))
                    if (editing) SelectionButton(slot, selected, onSelect)
                }
                MealTitle(slot, editing)
                if (editing) EditControls(slot, onSchedule) else ScheduleButton(slot, plan, onSchedule)
            }
            else -> Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                MealPhoto(slot, 148, editing)
                Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        Box(Modifier.weight(1f)) { MealTitle(slot, editing) }
                        if (editing) SelectionButton(slot, selected, onSelect)
                    }
                    if (editing) EditControls(slot, onSchedule, plan) else ScheduleButton(slot, plan, onSchedule)
                }
            }
        }
    }
}

@Composable
private fun MealTitle(slot: PlanSlot, editing: Boolean) {
    val nav = LocalNav.current
    Column(Modifier.fillMaxWidth().clickable { nav.push(Route.Recipe(slot.recipeId)) }, verticalArrangement = Arrangement.spacedBy(4.dp)) {
        RecipeCardName(slot.recipeName)
        if (!editing) RecipeCardServings(slot.servings)
    }
}

/** `side` locks a square of that size. Null fills the column and stays square. */
@Composable
private fun MealPhoto(slot: PlanSlot, side: Int?, editing: Boolean) {
    val store = LocalStore.current
    val nav = LocalNav.current
    Box(
        (if (side != null) Modifier.size(side.dp) else Modifier.fillMaxWidth().aspectRatio(1f))
            .clip(RoundedCornerShape(12.dp)).clickable { nav.push(Route.Recipe(slot.recipeId)) },
    ) {
        RecipePhoto(slot.photoPath, fill = true, corner = 12.dp)
        if (!editing) {
            Box(
                Modifier.align(Alignment.TopEnd).size(44.dp).clickable { store.launch { toggleCooked(slot) } }
                    .semantics { contentDescription = if (slot.cooked) "Mark not cooked" else "Mark cooked" },
                contentAlignment = Alignment.Center,
            ) {
                Icon(
                    if (slot.cooked) Icons.Filled.CheckCircle else Icons.Outlined.RadioButtonUnchecked, null,
                    tint = if (slot.cooked) Theme.accent else Color.White,
                    modifier = Modifier.size(24.dp).shadow(2.dp, CircleShape, ambientColor = Color.Black, spotColor = Color.Black.copy(alpha = 0.35f)),
                )
            }
        }
    }
}

@Composable
private fun SelectionButton(slot: PlanSlot, selected: Boolean, onSelect: () -> Unit) {
    Box(
        Modifier.size(width = 32.dp, height = 44.dp).clickable(onClick = onSelect)
            .semantics { contentDescription = "Select ${slot.recipeName}" },
        contentAlignment = Alignment.Center,
    ) {
        Icon(
            if (selected) Icons.Filled.CheckBox else Icons.Outlined.CheckBoxOutlineBlank, null,
            tint = if (selected) Theme.accent else Theme.muted, modifier = Modifier.size(24.dp),
        )
    }
}

@Composable
private fun EditControls(slot: PlanSlot, onSchedule: () -> Unit, plan: Plan? = null) {
    val store = LocalStore.current
    val current = plan ?: store.plan
    Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
        Flow(8.dp) {
            if (current != null) ScheduleButton(slot, current, onSchedule)
            ThumbsControl(slot.rating ?: 0, slot.recipeName) { next -> store.launch { rateMeal(slot, next) } }
        }
        ServingsControl(slot)
        if ((slot.rating ?: 0) > 0) Text("We'll suggest more like this", style = Theme.subtitle, color = Theme.muted)
        if ((slot.rating ?: 0) < 0) StarTip("plan.disliked")
    }
}

@Composable
private fun ScheduleButton(slot: PlanSlot, plan: Plan, onClick: () -> Unit) {
    Row(
        Modifier.heightIn(min = if (isAccessibilitySize) 44.dp else 36.dp).clip(RoundedCornerShape(10.dp)).background(Theme.surface)
            .border(1.dp, Theme.line, RoundedCornerShape(10.dp)).clickable(onClick = onClick)
            .semantics { contentDescription = "Schedule ${slot.recipeName}" }.padding(horizontal = 8.dp),
        verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp),
    ) {
        Icon(Icons.Outlined.CalendarToday, null, tint = Theme.accent, modifier = Modifier.size(15.dp))
        Text(scheduleLabel(slot, plan), style = Theme.subtitle, color = Theme.accent)
    }
}

/** − count + in one box. */
@Composable
private fun ServingsControl(slot: PlanSlot) {
    val store = LocalStore.current
    Row(
        Modifier.clip(RoundedCornerShape(10.dp)).background(Theme.surface).border(1.dp, Theme.line, RoundedCornerShape(10.dp)),
        verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(2.dp),
    ) {
        IconAction(Icons.Filled.Remove, "Decrease servings for ${slot.recipeName}", tint = Theme.accent, size = 16.dp, enabled = slot.servings > 1) {
            store.launch { setServings(slot, slot.servings - 1) }
        }
        Text("${slot.servings} servings", style = Theme.count, color = Theme.ink, textAlign = TextAlign.Center)
        IconAction(Icons.Filled.Add, "Increase servings for ${slot.recipeName}", tint = Theme.accent, size = 16.dp, enabled = slot.servings < 50) {
            store.launch { setServings(slot, slot.servings + 1) }
        }
    }
}

/** Pick a day for a meal; choosing a date saves it at once. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun ScheduleMealSheet(slot: PlanSlot) {
    val store = LocalStore.current
    val dismiss = LocalDismiss.current
    val today = LocalDate.now()
    val start = planDate(store.plan?.startDate ?: "")
    val earliest = if (start != null && start.isAfter(today)) start else today
    val initial = slot.dayIndex?.let { d -> start?.plusDays(d.toLong())?.takeIf { !it.isBefore(earliest) } } ?: earliest
    fun millis(date: LocalDate) = date.atStartOfDay(ZoneOffset.UTC).toInstant().toEpochMilli()
    val state = rememberDatePickerState(
        initialSelectedDateMillis = millis(initial),
        selectableDates = object : SelectableDates {
            override fun isSelectableDate(utcTimeMillis: Long) = utcTimeMillis >= millis(earliest)
        },
    )
    LaunchedEffect(state.selectedDateMillis) {
        val picked = state.selectedDateMillis ?: return@LaunchedEffect
        if (picked == millis(initial)) return@LaunchedEffect
        val date = Instant.ofEpochMilli(picked).atZone(ZoneOffset.UTC).toLocalDate()
        if (store.schedule(slot, date)) dismiss()
    }
    Column(Modifier.fillMaxWidth().background(Theme.bg)) {
        SheetBar("Schedule meal")
        Column(Modifier.verticalScroll(rememberScrollState()).padding(16.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
            Text(slot.recipeName, style = Theme.mealName, color = Theme.ink)
            DatePicker(
                state = state, title = null, headline = null, showModeToggle = false,
                colors = DatePickerDefaults.colors(
                    containerColor = Theme.bg, selectedDayContainerColor = Theme.accent, todayDateBorderColor = Theme.accent,
                    todayContentColor = Theme.accent, dayContentColor = Theme.ink,
                ),
            )
            store.error?.let { ErrorBanner(it) }
            LinkButton("Unschedule") { store.launch { unschedule(slot); dismiss() } }
        }
    }
}

/** Drafts to start from, and plans you approved or finished. */
@Composable
fun SavedPlansView() {
    val store = LocalStore.current
    val nav = LocalNav.current
    val dismiss = LocalDismiss.current
    var deleting by remember { mutableStateOf<SavedPlan?>(null) }
    var plans by remember { mutableStateOf<List<SavedPlan>>(emptyList()) }
    var error by remember { mutableStateOf<String?>(null) }
    var loading by remember { mutableStateOf(true) }

    LaunchedEffect(Unit) {
        try { plans = Api.get<PlanList>("plans").plans } catch (e: Throwable) { if (!Api.isCancellation(e)) error = Api.message(e) }
        loading = false
    }
    val drafts = plans.filter { it.status == "draft" }
    val history = plans.filter { (it.status != "draft" && it.status != "active") || it.decision != null }

    Column(Modifier.fillMaxSize().background(Theme.bg)) {
        SheetBar("Saved plans", cancel = "Close", onCancel = dismiss)
        ThemeList {
            error?.let { Box(Modifier.padding(16.dp)) { ErrorBanner(it) } }
            if (loading) Spinner()
            ListHeader("Drafts")
            if (!loading && drafts.isEmpty()) {
                ListRow { Muted("No drafts yet. Use ⋯ → Save as draft to keep a plan for later.", style = Theme.body) }
            }
            for (plan in drafts) {
                ListRow(chevron = false) {
                    Box(Modifier.weight(1f).clickable { store.launch { if (newPlan(source = plan.id)) dismiss() } }) { SavedPlanRow(plan) }
                    DeletePlanButton(plan) { deleting = plan }
                }
            }
            ListHeader("Plan history")
            if (!loading && history.isEmpty()) {
                ListRow { Muted("No past plans yet. Plans you approve or finish show up here.", style = Theme.body) }
            }
            for (plan in history) {
                ListRow(chevron = false) {
                    Box(Modifier.weight(1f).clickable { nav.push(Route.PlanHistory(plan, heading(plan))) }) { SavedPlanRow(plan) }
                    if (plan.status != "active") DeletePlanButton(plan) { deleting = plan }
                }
            }
        }
    }
    deleting?.let { plan ->
        RemovalConfirmation("Delete this plan?", heading(plan), "Delete plan", onDismiss = { deleting = null }) {
            try {
                Api.send<Ok>("plans/${plan.id}", "DELETE")
                plans = plans.filter { it.id != plan.id }
            } catch (e: Throwable) {
                error = Api.message(e)
            }
        }
    }
}

/** The meals of a past plan. */
@Composable
fun PlanHistoryView(plan: SavedPlan, title: String) {
    val nav = LocalNav.current
    Column(Modifier.fillMaxSize()) {
        NavBar(title)
        ThemeList {
            for (slot in plan.slots) {
                ListRow(onClick = { nav.push(Route.Recipe(slot.recipeId)) }) {
                    Column {
                        RecipeCardName(slot.recipeName)
                        Text("${slot.servings} servings · ${if (slot.cooked) "Cooked" else "Not cooked"}", style = Theme.subtitle, color = Theme.ink)
                    }
                }
            }
        }
    }
}

@Composable
private fun SavedPlanRow(plan: SavedPlan) {
    Column(Modifier.fillMaxWidth().padding(vertical = 4.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
        Text(heading(plan), style = Theme.mealName, color = Theme.ink)
        val parts = listOfNotNull(dateRange(plan), "${plan.slots.size} ${if (plan.slots.size == 1) "meal" else "meals"}", statusWord(plan))
        Text(parts.joinToString(" · "), style = Theme.subtitle, color = Theme.ink)
        if (plan.slots.isNotEmpty()) Text(mealsLine(plan), style = Theme.subtitle, color = Theme.muted, maxLines = 2)
        savedLine(plan)?.let { Text(it, style = Theme.subtitle, color = Theme.muted) }
    }
}

@Composable
private fun DeletePlanButton(plan: SavedPlan, onClick: () -> Unit) {
    IconAction(Icons.Outlined.Delete, "Delete ${heading(plan)}", tint = Theme.accent, onClick = onClick)
}

private fun heading(plan: SavedPlan): String {
    val title = plan.title.trim()
    if (title.isNotEmpty() && title != "This week") return title
    val start = planDate(plan.startDate) ?: return "Plan"
    return "Week of ${shortDate(start)}"
}

private fun dateRange(plan: SavedPlan): String {
    val start = planDate(plan.startDate) ?: return plan.startDate
    val end = start.plusDays((maxOf(plan.days, 1) - 1).toLong())
    return "${shortDate(start)} – ${shortDate(end)}"
}

private fun statusWord(plan: SavedPlan): String? {
    when (plan.decision) {
        "approve" -> return "Approved"
        "decline" -> return "Declined"
    }
    return when (plan.status) {
        "draft" -> null
        "active" -> "Current plan"
        "suggested" -> "Waiting for review"
        else -> plan.status.replaceFirstChar { it.titlecase(Locale.getDefault()) }
    }
}

private fun mealsLine(plan: SavedPlan): String {
    val names = plan.slots.map { it.recipeName }
    val shown = names.take(3).joinToString(", ")
    return if (names.size > 3) "$shown +${names.size - 3} more" else shown
}

private val savedFormat = DateTimeFormatter.ofPattern("MMM d, h:mm a", Locale.getDefault())

private fun savedLine(plan: SavedPlan): String? {
    val raw = plan.createdAt ?: return null
    val date = try { OffsetDateTime.parse(raw).atZoneSameInstant(ZoneId.systemDefault()) } catch (_: Exception) { return null }
    return "Saved ${date.format(savedFormat)}"
}

/** Review a suggested plan: rounded photos with a swap button, the name and cook time. */
@Composable
fun SuggestedPlanReview() {
    val store = LocalStore.current
    val nav = LocalNav.current
    val dismiss = LocalDismiss.current
    val scope = rememberCoroutineScope()
    var swapping by remember { mutableStateOf<PlanSlot?>(null) }
    var busy by remember { mutableStateOf(false) }
    var reporting by remember { mutableStateOf(false) }
    var reportNote by remember { mutableStateOf("") }
    var reportedId by remember { mutableStateOf<Int?>(null) }
    val large = isAccessibilitySize

    fun run(work: suspend () -> Unit) {
        busy = true
        scope.launch { try { work() } finally { busy = false } }
    }

    val proposal = store.proposal
    val disabled = busy || store.generatingProposal
    Column(Modifier.fillMaxSize().background(Theme.bg)) {
        SheetBar("Review your suggestions", cancel = "Close", onCancel = { store.proposalError = null; dismiss() })
        Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            if (store.generatingProposal) {
                Column(Modifier.fillMaxWidth().heightIn(min = 80.dp), horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.Center) {
                    CircularProgressIndicator(color = Theme.muted, strokeWidth = 2.dp, modifier = Modifier.size(24.dp))
                    Text("Finding meals…", style = Theme.body, color = Theme.muted)
                }
            }
            val count = proposal?.slots?.size ?: 4
            val minimum = maxOf(1, (proposal?.slots?.size ?: 0) - (proposal?.suggestedRecipeIds?.size ?: 0))
            Row(Modifier.fillMaxWidth().alpha(if (proposal?.status == "suggested") 1f else 0.4f), verticalAlignment = Alignment.CenterVertically) {
                Text("$count meals", style = Theme.mealName, color = Theme.ink, modifier = Modifier.weight(1f))
                Stepper(count, minimum..14, "meals") { next -> if (proposal?.status == "suggested" && !disabled) run { store.resizeProposal(next) } }
            }
            store.proposalError?.let {
                ErrorBanner(it)
                LinkButton("Dismiss error") { store.proposalError = null }
            }
            val slots = proposal?.slots ?: emptyList()
            for (row in slots.chunked(if (large) 1 else 2)) {
                Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                    for (slot in row) Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        val suggested = proposal?.suggestedRecipeIds?.contains(slot.recipeId) == true
                        Box(Modifier.fillMaxWidth().aspectRatio(1f).clip(RoundedCornerShape(14.dp)).clickable { nav.push(Route.Recipe(slot.recipeId)) }) {
                            RecipePhoto(slot.photoPath, fill = true, corner = 14.dp)
                            if (suggested) {
                                Box(
                                    Modifier.align(Alignment.TopEnd).padding(6.dp).size(44.dp).shadow(3.dp, CircleShape).background(Theme.surface, CircleShape)
                                        .clickable(enabled = proposal?.status == "suggested" && !disabled) { swapping = slot }
                                        .semantics { contentDescription = "Swap meal: ${slot.recipeName}" },
                                    contentAlignment = Alignment.Center,
                                ) { Icon(Icons.Filled.Sync, null, tint = Theme.accent, modifier = Modifier.size(22.dp)) }
                            }
                        }
                        Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                            RecipeCardName(slot.recipeName)
                            slot.cookingMinutes?.let { Text("$it min", style = Theme.subtitle, color = Theme.muted) }
                            if (!suggested) Text("Your selection", style = Theme.subtitle, color = Theme.muted)
                        }
                    }
                    if (row.size == 1 && !large) Spacer(Modifier.weight(1f))
                }
            }
            val actions: @Composable (Modifier) -> Unit = { m ->
                if (proposal?.status == "suggested") {
                    FilledButton("Approve plan", m, enabled = !disabled) { run { store.reviewProposal("approve") } }
                    OutlinedButton("Suggest another", m, enabled = !disabled) { run { store.reviewProposal("decline") } }
                } else {
                    OutlinedButton("Try another suggestion", m, enabled = !disabled) { run { store.newPlan(meals = 4) } }
                }
            }
            if (large) Column(Modifier.padding(top = 4.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) { actions(Modifier) }
            else Row(Modifier.padding(top = 4.dp), horizontalArrangement = Arrangement.spacedBy(10.dp)) { actions(Modifier.weight(1f)) }
            Row(
                Modifier.fillMaxWidth().heightIn(min = 44.dp).clickable { nav.push(Route.TasteLab(swipe = true)) },
                horizontalArrangement = Arrangement.spacedBy(8.dp, Alignment.CenterHorizontally), verticalAlignment = Alignment.CenterVertically,
            ) {
                Icon(Icons.Outlined.Gesture, null, tint = Theme.accent)
                Text("Improve suggestions", style = Theme.action, color = Theme.accent)
            }
            if (proposal != null && reportedId == proposal.id) {
                Text("Thanks. We'll look at why these were suggested.", style = Theme.subtitle, color = Theme.muted, textAlign = TextAlign.Center, modifier = Modifier.fillMaxWidth())
            } else if (proposal != null) {
                Row(
                    Modifier.fillMaxWidth().heightIn(min = 44.dp).clickable { reportNote = ""; reporting = true },
                    horizontalArrangement = Arrangement.spacedBy(8.dp, Alignment.CenterHorizontally), verticalAlignment = Alignment.CenterVertically,
                ) {
                    Icon(Icons.Outlined.Flag, null, tint = Theme.muted)
                    Text("Report this suggestion", style = Theme.action, color = Theme.muted)
                }
            }
        }
    }
    DisposableCleanup { store.proposalError = null }
    swapping?.let { slot -> Sheet(onDismiss = { swapping = null }) { ProposalSwapPicker(slot) } }
    if (reporting) {
        Sheet(onDismiss = { reporting = false }) {
            Column(Modifier.fillMaxSize().background(Theme.bg)) {
                SheetBar("Report this suggestion", onCancel = { reporting = false })
                Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                    Text("What's wrong with this plan?", style = Theme.action, color = Theme.ink)
                    TextBox(reportNote, { reportNote = it }, "e.g. Three chicken dinners in a row, and none of us eat olives", style = Theme.subtitle, minLines = 3)
                    FilledButton(if (busy) "Sending…" else "Send report", enabled = !busy) {
                        val id = store.proposal?.id
                        run { if (store.reportProposal(reportNote.trim())) { reportedId = id; reporting = false } }
                    }
                }
            }
        }
    }
}

/** Runs `onDispose` when the screen leaves (SwiftUI `.onDisappear`). */
@Composable
fun DisposableCleanup(onDispose: () -> Unit) {
    androidx.compose.runtime.DisposableEffect(Unit) { onDispose { onDispose() } }
}

/** Confirm a removal in a short sheet with a red button. */
@Composable
fun RemovalConfirmation(title: String, message: String, actionTitle: String, onDismiss: () -> Unit, action: suspend () -> Unit) {
    var busy by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()
    Sheet(onDismiss = onDismiss, full = isAccessibilitySize) {
        val dismiss = LocalDismiss.current
        Column(
            Modifier.fillMaxWidth().verticalScroll(rememberScrollState()).padding(20.dp).alpha(if (busy) 0.6f else 1f),
            horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(16.dp),
        ) {
            Text(title, style = Theme.title, color = Theme.ink, textAlign = TextAlign.Center)
            Text(message, style = Theme.body, color = Theme.muted, textAlign = TextAlign.Center)
            FilledButton(actionTitle, color = Theme.destructive, textColor = Color.White, enabled = !busy, minHeight = 44.dp, shape = RoundedCornerShape(10.dp)) {
                busy = true
                scope.launch { action(); dismiss() }
            }
            LinkButton("Cancel", Modifier.fillMaxWidth(), enabled = !busy) { dismiss() }
        }
    }
}

/** Search for a meal to swap in for one suggestion. */
@Composable
private fun ProposalSwapPicker(slot: PlanSlot) {
    val store = LocalStore.current
    val dismiss = LocalDismiss.current
    val scope = rememberCoroutineScope()
    val sheetNav = remember { Nav(Route.PlanHome) }
    var query by remember { mutableStateOf("") }
    var options by remember { mutableStateOf<List<SwapOption>>(emptyList()) }
    var loading by remember { mutableStateOf(false) }
    var saving by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }

    LaunchedEffect(query) {
        loading = true
        try {
            delay(250)
            val plan = store.proposal ?: return@LaunchedEffect
            options = Api.get<SwapOptions>("plans/${plan.id}/swap-options/${slot.id}", mapOf("q" to query), reportErrors = false).recipes
            error = null
        } catch (e: Throwable) {
            if (!Api.isCancellation(e)) error = Api.message(e)
        } finally {
            loading = false
        }
    }

    NavStack(sheetNav) { route ->
        if (route != Route.PlanHome) { RouteContent(route); return@NavStack }
        Column(Modifier.fillMaxSize().background(Theme.bg)) {
            SheetBar("Choose a replacement")
            Column(Modifier.verticalScroll(rememberScrollState()).padding(16.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
                Text("Replace ${slot.recipeName}", style = Theme.subtitle, color = Theme.muted)
                TextBox(query, { query = it }, "Search meals or ingredients", contentDescription = "Search replacement meals")
                error?.let { ErrorBanner(it) }
                if (loading) Spinner()
                if (!loading && options.isEmpty() && error == null) {
                    Text("No matching meals. Try another search or adjust your filters.", style = Theme.body, color = Theme.ink)
                    LinkButton("Adjust filters") { sheetNav.push(Route.Filters) }
                }
                for (option in options) {
                    Row(
                        Modifier.fillMaxWidth().clickable(enabled = !saving && !loading) {
                            saving = true
                            scope.launch {
                                store.swapProposal(slot, option.id)
                                saving = false
                                if (store.proposalError == null) dismiss() else { error = store.proposalError; store.proposalError = null }
                            }
                        },
                        horizontalArrangement = Arrangement.spacedBy(12.dp),
                    ) {
                        Box(Modifier.size(70.dp)) { RecipePhoto(option.photoPath, fill = true, corner = 12.dp) }
                        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                            RecipeCardName(option.name)
                            option.cookingMinutes?.let { Text("$it min", style = Theme.subtitle, color = Theme.muted) }
                        }
                    }
                    Hairline()
                }
            }
        }
    }
}
