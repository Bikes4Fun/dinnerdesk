package build.computerscience.dinnerdesk.ui

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.slideInVertically
import androidx.compose.animation.slideOutVertically
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.BoxScope
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.RemoveCircle
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.text.style.TextDecoration
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.delay

/**
 * What a recipe card's + or check just did. Those icons have no room for a label (#35), so the
 * bar says it in words and offers one Undo. It mirrors the Prep tab's check-off bar, and web and
 * iPhone show the same thing.
 */
@Composable
fun BoxScope.PlanToastBar() {
    val store = LocalStore.current
    val toast = store.planToast
    val view = LocalView.current

    LaunchedEffect(toast) {
        val shown = toast ?: return@LaunchedEffect
        // TalkBack doesn't move to a bar that appears on its own, so say it out loud.
        view.announceForAccessibility(shown.text)
        delay(4000)
        if (store.planToast?.id == shown.id) store.planToast = null
    }

    AnimatedVisibility(
        toast != null, Modifier.align(Alignment.BottomCenter),
        enter = slideInVertically { it } + fadeIn(), exit = slideOutVertically { it } + fadeOut(),
    ) {
        val shown = toast ?: return@AnimatedVisibility
        Row(
            Modifier.padding(horizontal = 12.dp).padding(bottom = 12.dp).fillMaxWidth()
                .shadow(14.dp, RoundedCornerShape(20.dp), spotColor = Theme.ink.copy(alpha = 0.25f))
                .background(Theme.ink, RoundedCornerShape(20.dp))
                .padding(start = 16.dp, end = 6.dp, top = 8.dp, bottom = 8.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            Icon(
                if (shown.undoAdds) Icons.Filled.RemoveCircle else Icons.Filled.CheckCircle, null,
                tint = Theme.coral, modifier = Modifier.size(20.dp),
            )
            Text(shown.text, style = Theme.subtitle, color = Theme.surface, maxLines = 2, modifier = Modifier.weight(1f))
            Text(
                "Undo", style = Theme.action.copy(textDecoration = TextDecoration.Underline), color = Theme.coralTint,
                modifier = Modifier.heightIn(min = 44.dp)
                    .clickable { store.launch { undoPlanToast() } }.padding(top = 11.dp),
            )
            IconAction(Icons.Filled.Close, "Dismiss", tint = Theme.aubergineTint, size = 18.dp) {
                store.planToast = null
            }
        }
    }
}
