package build.computerscience.dinnerdesk.ui

import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.isImeVisible
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.outlined.Assignment
import androidx.compose.material.icons.automirrored.outlined.MenuBook
import androidx.compose.material.icons.outlined.CalendarToday
import androidx.compose.material.icons.outlined.MoreHoriz
import androidx.compose.material.icons.outlined.ShoppingCart
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateMapOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.selected
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.compose.LifecycleEventEffect
import build.computerscience.dinnerdesk.data.ResponseCache
import kotlinx.coroutines.launch

/** Who is using the app decides what shows: loading, sign-in, or the tabs (AuthGate in AuthView.swift). */
@Composable
fun AuthGate(content: @Composable () -> Unit) {
    val session = LocalSession.current
    val scope = rememberCoroutineScope()
    var guestNoticeDismissed by rememberSaveable { mutableStateOf(false) }
    var showSignIn by remember { mutableStateOf(false) }

    LaunchedEffect(Unit) { session.refresh() }
    LifecycleEventEffect(Lifecycle.Event.ON_RESUME) { scope.launch { session.refresh() } }

    Box(Modifier.fillMaxSize().background(Theme.bg).statusBarsPadding()) {
        val status = session.status
        when {
            status == null -> Column(
                Modifier.fillMaxSize().padding(24.dp), verticalArrangement = Arrangement.spacedBy(16.dp, Alignment.CenterVertically),
                horizontalAlignment = Alignment.CenterHorizontally,
            ) {
                val err = session.loadError
                if (err != null) {
                    Text(err, color = Theme.muted, textAlign = TextAlign.Center, style = Theme.body)
                    AccentButton("Try again", Modifier.widthIn(max = 220.dp)) { scope.launch { session.refresh() } }
                } else {
                    CircularProgressIndicator(color = Theme.muted, strokeWidth = 2.dp, modifier = Modifier.size(28.dp))
                }
            }
            session.needsSignIn -> AuthView()
            else -> {
                Column(Modifier.fillMaxSize()) {
                    if (status.authenticated != true && !guestNoticeDismissed) {
                        Column(Modifier.fillMaxWidth().background(Theme.bg).padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                            Text("Guest data can be lost if you reinstall the app. Create an account to protect it.", style = Theme.subtitle, color = Theme.muted)
                            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                                Text("Sign in or create account", style = Theme.subtitle, color = Theme.accent, modifier = Modifier.clickable { showSignIn = true })
                                Text("Dismiss", style = Theme.subtitle, color = Theme.accent, modifier = Modifier.clickable { guestNoticeDismissed = true })
                            }
                        }
                    }
                    Box(Modifier.weight(1f)) {
                        content()
                        session.loadError?.let { ErrorBanner(it, Modifier.padding(16.dp)) }
                    }
                }
                LaunchedEffect(status.householdId) { session.checkTour() }
                if (showSignIn) {
                    Sheet(onDismiss = { showSignIn = false; scope.launch { session.checkTour() } }) { AuthView(isSheet = true) }
                }
            }
        }
        if (session.showTour) TourView()
    }
}

/** The five tabs. Tapping a tab (or a link to one) always shows its first screen. */
@OptIn(ExperimentalLayoutApi::class)
@Composable
fun ContentView() {
    val store = LocalStore.current
    val scope = rememberCoroutineScope()
    var tab by rememberSaveable { mutableStateOf(AppTab.Plan) }
    val navs = remember { mutableStateMapOf<AppTab, Nav>() }

    fun rootOf(t: AppTab) = when (t) {
        AppTab.Plan -> Route.PlanHome
        AppTab.Recipes -> Route.RecipesHome
        AppTab.Grocery -> Route.GroceryHome
        AppTab.Prep -> Route.PrepHome
        AppTab.More -> Route.MoreHome
    }

    // Reset the destination before showing it, including when the current tab is tapped.
    fun showTab(next: AppTab) {
        navs[next] = Nav(rootOf(next))
        store.error = null
        store.proposalError = null
        store.showingProposal = false
        tab = next
    }

    val showPrep = LocalConfiguration.current.screenWidthDp >= 390 && !isAccessibilitySize
    LaunchedEffect(showPrep) { if (!showPrep && tab == AppTab.Prep) showTab(AppTab.Plan) }

    LaunchedEffect(Unit) { store.loadAll(onlyIfStale = true) }
    LaunchedEffect(Unit) { ResponseCache.accountChanged.collect { store.switchAccount() } }
    LifecycleEventEffect(Lifecycle.Event.ON_RESUME) { scope.launch { store.loadAll(onlyIfStale = true) } }
    LifecycleEventEffect(Lifecycle.Event.ON_STOP) { showTab(AppTab.Plan) }

    val mealsLeft = store.plan?.slots?.count { !it.cooked } ?: 0
    val itemsLeft = store.grocery.count { !it.checked && !it.neverShop }
    val keyboard = WindowInsets.isImeVisible

    CompositionLocalProvider(LocalSelectTab provides { t: AppTab -> showTab(t) }) {
        Column(Modifier.fillMaxSize().background(Theme.bg)) {
            Box(Modifier.weight(1f).fillMaxWidth().imePadding()) {
                val nav = navs.getOrPut(tab) { Nav(rootOf(tab)) }
                androidx.compose.runtime.key(nav) {
                    NavStack(nav) { route -> RouteContent(route) }
                }
            }
            if (!keyboard) {
                TabBar(
                    selected = tab, showPrep = showPrep,
                    badges = mapOf(AppTab.Plan to mealsLeft, AppTab.Grocery to itemsLeft),
                    onSelect = { showTab(it) },
                )
            }
        }
        if (store.showingProposal) {
            Sheet(onDismiss = { store.proposalError = null; store.showingProposal = false }) {
                val sheetNav = remember { Nav(Route.PlanHome) }
                NavStack(sheetNav) { route ->
                    if (route == Route.PlanHome) SuggestedPlanReview() else RouteContent(route)
                }
            }
        }
    }
}

private data class TabSpec(val tab: AppTab, val title: String, val icon: ImageVector)

/** iOS-style tab bar: surface color, hairline on top, small labels, accent when selected. */
@Composable
private fun TabBar(selected: AppTab, showPrep: Boolean, badges: Map<AppTab, Int>, onSelect: (AppTab) -> Unit) {
    val specs = listOfNotNull(
        TabSpec(AppTab.Plan, "Plan", Icons.Outlined.CalendarToday),
        TabSpec(AppTab.Recipes, "Recipes", Icons.AutoMirrored.Outlined.MenuBook),
        TabSpec(AppTab.Grocery, "Grocery", Icons.Outlined.ShoppingCart),
        if (showPrep) TabSpec(AppTab.Prep, "Prep", Icons.AutoMirrored.Outlined.Assignment) else null,
        TabSpec(AppTab.More, "More", Icons.Outlined.MoreHoriz),
    )
    Column(Modifier.fillMaxWidth().background(Theme.surface)) {
        Hairline()
        Row(Modifier.fillMaxWidth().navigationBarsPadding().height(52.dp)) {
            for (spec in specs) {
                val on = spec.tab == selected
                val color = if (on) Theme.accent else Theme.muted
                Column(
                    Modifier.weight(1f).fillMaxSize().semantics { this.selected = on }
                        .clickable(interactionSource = remember { MutableInteractionSource() }, indication = null, role = Role.Tab) { onSelect(spec.tab) },
                    horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.Center,
                ) {
                    Box {
                        Icon(spec.icon, null, tint = color, modifier = Modifier.size(25.dp))
                        val badge = badges[spec.tab] ?: 0
                        if (badge > 0) {
                            Box(
                                Modifier.align(Alignment.TopEnd).offset(x = 12.dp, y = (-4).dp).heightIn(min = 18.dp).widthIn(min = 18.dp)
                                    .background(if (on) Theme.accent else Theme.muted, CircleShape).padding(horizontal = 5.dp),
                                contentAlignment = Alignment.Center,
                            ) {
                                Text("$badge", color = Color.White, style = Theme.count.copy(fontSize = 12.sp, lineHeight = 14.sp))
                            }
                        }
                    }
                    Spacer(Modifier.height(2.dp))
                    Text(
                        spec.title, color = color, maxLines = 1,
                        style = Theme.count.copy(fontSize = 10.sp, fontWeight = if (on) FontWeight.Bold else FontWeight.Medium),
                    )
                }
            }
        }
    }
}

/** Which screen a route shows. */
@OptIn(ExperimentalFoundationApi::class)
@Composable
fun RouteContent(route: Route) {
    when (route) {
        Route.PlanHome -> PlanView()
        Route.RecipesHome -> RecipesView()
        Route.GroceryHome -> GroceryView()
        Route.PrepHome -> PrepView()
        Route.MoreHome -> MoreView()
        is Route.Recipe -> RecipeDetailView(route.id)
        is Route.RecipeGrid -> RecipeGridPage(route.title, route.recipes)
        is Route.GroceryItem -> GroceryItemView(route.lineId)
        Route.GroceryStores -> GroceryStoreView()
        Route.AisleOrder -> AisleOrderView()
        Route.Kitchen -> KitchenView()
        Route.Pantry -> PantryView()
        is Route.PantryItem -> PantryItemEditor(route.item, route.onChanged)
        Route.AlwaysChecked -> AlwaysCheckedView()
        Route.Substitutions -> SubstitutionsView()
        Route.Filters -> FiltersView()
        Route.HiddenRecipes -> HiddenRecipesView()
        Route.MyRecipes -> MyRecipesView()
        is Route.TasteLab -> TasteLabView(route.swipe)
        Route.Settings -> SettingsView()
        Route.Account -> AccountView()
        Route.Privacy -> PrivacyView()
        Route.Feedback -> FeedbackView()
        is Route.PlanHistory -> PlanHistoryView(route.plan, route.title)
    }
}
