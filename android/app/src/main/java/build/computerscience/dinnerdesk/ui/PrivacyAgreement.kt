package build.computerscience.dinnerdesk.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import build.computerscience.dinnerdesk.data.Api
import build.computerscience.dinnerdesk.data.AuthApi
import build.computerscience.dinnerdesk.data.Copy
import kotlinx.coroutines.launch

/**
 * The first-open privacy screen. Shows until this guest kitchen (or account) agrees to the current
 * privacy version (auth/status privacy_agreed). "I understand, continue" is the agreement.
 * Same screen as the website's PrivacyAgreement.jsx and iOS PrivacyAgreementView.
 */
@Composable
fun PrivacyAgreement() {
    val session = LocalSession.current
    val scope = rememberCoroutineScope()
    var busy by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    var showPrivacy by remember { mutableStateOf(false) }
    val signedIn = session.status?.authenticated == true

    fun agree() {
        busy = true
        error = null
        scope.launch {
            try {
                AuthApi.agreeToPrivacy()
                session.refresh()
            } catch (e: Throwable) {
                error = Api.message(e)
            } finally {
                busy = false
            }
        }
    }

    Column(
        Modifier.fillMaxSize().background(Theme.bg).statusBarsPadding().navigationBarsPadding()
            .verticalScroll(rememberScrollState()).padding(20.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        Text(Copy.appName, style = Theme.action, color = Theme.accent)
        Text(Copy.text("privacy.agree.title"), style = Theme.bigTitle, color = Theme.ink)
        Text(Copy.text(if (signedIn) "privacy.agree.updated" else "privacy.agree.guest"), style = Theme.body, color = Theme.ink)

        PrivacySummary(compact = true)

        if (!signedIn) {
            Text(
                Copy.text("privacy.agree.device"), style = Theme.subtitle, color = Theme.accent,
                modifier = Modifier.fillMaxWidth().background(Theme.aubergineTint, RoundedCornerShape(12.dp)).padding(12.dp),
            )
        }
        error?.let { ErrorBanner(it) }

        Box(
            Modifier.fillMaxWidth().heightIn(min = 52.dp).clip(CircleShape).background(Theme.ink)
                .clickable(enabled = !busy, role = Role.Button) { agree() },
            contentAlignment = Alignment.Center,
        ) {
            if (busy) CircularProgressIndicator(color = Theme.bg, strokeWidth = 2.dp, modifier = Modifier.size(20.dp))
            else Text(Copy.text("privacy.agree.button"), style = Theme.action, color = Theme.bg)
        }
        Text(
            Copy.text("privacy.agree.fine"), style = Theme.subtitle, color = Theme.muted,
            textAlign = TextAlign.Center, modifier = Modifier.fillMaxWidth(),
        )
        Column(Modifier.fillMaxWidth(), horizontalAlignment = Alignment.CenterHorizontally) {
            Text(
                Copy.text("privacy.agree.read"), style = Theme.action, color = Theme.accent,
                modifier = Modifier.heightIn(min = 44.dp).clickable(role = Role.Button) { showPrivacy = true }.padding(10.dp),
            )
            if (!signedIn) {
                // Back to the sign-in screen, which has Create account.
                Text(
                    "Create an account instead", style = Theme.action, color = Theme.accent,
                    modifier = Modifier.heightIn(min = 44.dp).clickable(role = Role.Button) { session.guest = false }.padding(10.dp),
                )
            }
        }
    }
    if (showPrivacy) PrivacyPolicyDialog { showPrivacy = false }
}
