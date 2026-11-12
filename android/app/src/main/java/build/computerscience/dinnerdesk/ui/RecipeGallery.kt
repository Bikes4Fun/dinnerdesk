package build.computerscience.dinnerdesk.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import build.computerscience.dinnerdesk.data.RecipeDetail

@Composable
fun RecipeGallery(recipe: RecipeDetail) {
    val photos = recipe.galleryPhotos
    var active by remember(recipe.id, photos.map { it.path }) { mutableStateOf(0) }
    val photo = photos.getOrNull(active)
    var creditOpen by remember(photo?.path) { mutableStateOf(false) }
    val openUrl = rememberOpenUrl()
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Box {
            RecipePhoto(photo?.path, large = true)
            if (photo != null) TextButton(onClick = { creditOpen = true },
                modifier = Modifier.align(Alignment.BottomEnd).padding(8.dp).size(44.dp)
                    .background(Color.White.copy(alpha = 0.9f), CircleShape)
                    .semantics { contentDescription = "Photo source" }) { Text("i", color = Theme.ink) }
        }
        if (photos.size > 1) Row(verticalAlignment = Alignment.CenterVertically) {
            TextButton(onClick = { active-- }, enabled = active > 0,
                modifier = Modifier.semantics { contentDescription = "Previous photo" }) { Text("←") }
            Text("${active + 1} / ${photos.size}", style = Theme.subtitle)
            TextButton(onClick = { active++ }, enabled = active < photos.lastIndex,
                modifier = Modifier.semantics { contentDescription = "Next photo" }) { Text("→") }
        }
        if (photo?.ai == true) StarTip("recipes.ai-photo")
        else if (photo?.shared == true) StarTip("recipes.shared-photo")
    }
    if (creditOpen && photo != null) AlertDialog(
        onDismissRequest = { creditOpen = false },
        title = { Text("Photo source") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text(photo.credit?.takeIf { it.isNotBlank() } ?: "Photo source not recorded")
                photo.sourceLink?.let { link -> TextButton(onClick = { openUrl(link) }) { Text("View source") } }
            }
        },
        confirmButton = { TextButton(onClick = { creditOpen = false }) { Text("Done") } },
    )
}
