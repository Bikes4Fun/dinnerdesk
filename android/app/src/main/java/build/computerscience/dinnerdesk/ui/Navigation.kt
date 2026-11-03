package build.computerscience.dinnerdesk.ui

import androidx.activity.compose.BackHandler
import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.core.tween
import androidx.compose.animation.slideInHorizontally
import androidx.compose.animation.slideOutHorizontally
import androidx.compose.animation.togetherWith
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.compositionLocalOf
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.saveable.rememberSaveableStateHolder
import androidx.compose.runtime.snapshotFlow
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.Modifier
import build.computerscience.dinnerdesk.data.ItemPlacement
import build.computerscience.dinnerdesk.data.KitchenPantryItem
import build.computerscience.dinnerdesk.data.RecipeSummary
import build.computerscience.dinnerdesk.data.SavedPlan
import build.computerscience.dinnerdesk.data.Session
import build.computerscience.dinnerdesk.data.Store
import java.util.concurrent.atomic.AtomicLong

enum class AppTab { Plan, Recipes, Grocery, Prep, More }

/** Every pushed screen. Like a SwiftUI NavigationLink destination. */
sealed interface Route {
    data object PlanHome : Route
    data object RecipesHome : Route
    data object GroceryHome : Route
    data object PrepHome : Route
    data object MoreHome : Route
    data class Recipe(val id: Int) : Route
    data class RecipeGrid(val title: String, val recipes: List<RecipeSummary>) : Route
    data class GroceryItem(val lineId: Int) : Route
    data object GroceryStores : Route
    data object AisleOrder : Route
    data object Kitchen : Route
    data object Pantry : Route
    data class PantryItem(val item: KitchenPantryItem, val onChanged: suspend () -> Unit) : Route
    data object AlwaysChecked : Route
    data object Substitutions : Route
    data object Filters : Route
    data object HiddenRecipes : Route
    data object MyRecipes : Route
    data class TasteLab(val swipe: Boolean = false) : Route
    data object Settings : Route
    data object Account : Route
    data object Privacy : Route
    data object Feedback : Route
    data class PlanHistory(val plan: SavedPlan, val title: String) : Route
}

private val nextEntry = AtomicLong(1)

class NavEntry(val route: Route) {
    val id: Long = nextEntry.getAndIncrement()
}

/** One navigation stack: a tab's, or a sheet's. */
class Nav(root: Route) {
    internal val entries = mutableStateListOf(NavEntry(root))
    val canPop: Boolean get() = entries.size > 1
    fun push(route: Route) { entries.add(NavEntry(route)) }
    fun pop() { if (entries.size > 1) entries.removeAt(entries.lastIndex) }
}

val LocalNav = staticCompositionLocalOf<Nav> { error("No Nav") }
val LocalStore = staticCompositionLocalOf<Store> { error("No Store") }
val LocalSession = staticCompositionLocalOf<Session> { error("No Session") }
val LocalSelectTab = staticCompositionLocalOf<(AppTab) -> Unit> { {} }
/** Close this screen: pop it, or close the sheet it sits in (SwiftUI's `dismiss`). */
val LocalDismiss = compositionLocalOf<() -> Unit> { {} }

/** Renders the top screen, slides pushes in from the trailing edge, and keeps each screen's saved state. */
@Composable
fun NavStack(nav: Nav, modifier: Modifier = Modifier, content: @Composable (Route) -> Unit) {
    val holder = rememberSaveableStateHolder()
    val outerDismiss = LocalDismiss.current
    BackHandler(enabled = nav.canPop) { nav.pop() }
    LaunchedEffect(nav) {
        var known = nav.entries.map { it.id }.toSet()
        snapshotFlow { nav.entries.map { it.id }.toSet() }.collect { now ->
            for (gone in known - now) holder.removeState(gone)
            known = now
        }
    }
    val top = nav.entries.last()
    AnimatedContent(
        targetState = top,
        transitionSpec = {
            if (targetState.id > initialState.id) {
                slideInHorizontally(tween(280)) { it } togetherWith slideOutHorizontally(tween(280)) { -it / 3 }
            } else {
                slideInHorizontally(tween(280)) { -it / 3 } togetherWith slideOutHorizontally(tween(280)) { it }
            }
        },
        modifier = modifier.background(Theme.bg),
        label = "nav",
    ) { entry ->
        val isRoot = nav.entries.firstOrNull()?.id == entry.id
        CompositionLocalProvider(
            LocalNav provides nav,
            LocalDismiss provides (if (isRoot) outerDismiss else ({ nav.pop() })),
        ) {
            holder.SaveableStateProvider(entry.id) {
                Box(Modifier.fillMaxSize().background(Theme.bg)) { content(entry.route) }
            }
        }
    }
}
