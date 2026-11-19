package build.computerscience.dinnerdesk.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ChevronRight
import androidx.compose.material.icons.filled.Verified
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import build.computerscience.dinnerdesk.data.Copy

@Composable
fun ReviewedBadge(detail: Boolean = false) {
    var showing by remember { mutableStateOf(false) }
    val modifier = if (detail) Modifier.background(Theme.aubergineTint, CircleShape)
        .clickable(role = Role.Button) { showing = true }.heightIn(min = 44.dp).padding(horizontal = 12.dp) else Modifier
    Row(modifier.semantics(mergeDescendants = true) { contentDescription = Copy.text("recipe.reviewed.description") },
        verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(4.dp)) {
        Icon(Icons.Filled.Verified, null, tint = Theme.ink, modifier = Modifier.size(16.dp))
        Text(Copy.text("recipe.reviewed"), style = Theme.count, color = Theme.ink)
        if (detail) Icon(Icons.Filled.ChevronRight, null, tint = Theme.ink, modifier = Modifier.size(16.dp))
    }
    if (showing) Sheet(onDismiss = { showing = false }) {
        SheetBar(Copy.text("recipe.reviewed"), cancel = "Done")
        Text(Copy.text("recipe.kitchen-tested.explanation"), style = Theme.body, color = Theme.ink, modifier = Modifier.padding(24.dp))
    }
}

@Composable
fun RecipeStatusLine(minutes: Int?, reviewed: Boolean) {
    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(4.dp)) {
        if (minutes != null && minutes > 0) Text("$minutes min", style = Theme.count, color = Theme.muted)
        if (reviewed) {
            if (minutes != null && minutes > 0) Text("·", style = Theme.count, color = Theme.muted)
            ReviewedBadge()
        }
    }
}
