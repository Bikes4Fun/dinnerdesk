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
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.Email
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.input.KeyboardCapitalization
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import build.computerscience.dinnerdesk.data.Api
import build.computerscience.dinnerdesk.data.AuthApi
import build.computerscience.dinnerdesk.data.Copy
import kotlinx.coroutines.launch

private enum class AuthMode(val title: String) { SignIn(Copy.text("ui.sign.in")), SignUp(Copy.text("ui.create.account")) }

/** Sign in or create an account. `isSheet` when shown from Settings (adds Cancel). */
@Composable
fun AuthView(isSheet: Boolean = false) {
    val session = LocalSession.current
    val dismiss = LocalDismiss.current
    val scope = rememberCoroutineScope()
    var mode by rememberSaveable { mutableStateOf(AuthMode.SignIn) }
    var email by rememberSaveable { mutableStateOf("") }
    var password by remember { mutableStateOf("") }
    var householdName by rememberSaveable { mutableStateOf("") }
    var busy by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    var forgot by remember { mutableStateOf(false) }
    var agreedPrivacy by rememberSaveable { mutableStateOf(false) }
    var showPrivacy by remember { mutableStateOf(false) }

    val canSubmit = !busy && email.trim().length >= 3 && password.length >= (if (mode == AuthMode.SignUp) 8 else 1) &&
        (mode == AuthMode.SignIn || agreedPrivacy)
    val usernameOnly = mode == AuthMode.SignUp && email.trim().isNotEmpty() && !email.contains("@")

    fun submit() {
        busy = true
        error = null
        scope.launch {
            val cleanEmail = email.trim()
            try {
                if (mode == AuthMode.SignIn) {
                    AuthApi.login(cleanEmail, password)
                } else {
                    val name = householdName.trim()
                    AuthApi.signup(cleanEmail, password, name.ifEmpty { Copy.text("ui.my.household") }, agreedPrivacy)
                }
                password = ""
                session.refresh()
                if (isSheet) dismiss()
            } catch (e: Throwable) {
                error = Api.message(e)
            } finally {
                busy = false
            }
        }
    }

    Column(Modifier.fillMaxSize().background(Theme.bg)) {
        if (isSheet) SheetBar(title = "", cancel = "Cancel")
        Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(vertical = 8.dp)) {
            Column(Modifier.padding(horizontal = 32.dp, vertical = 16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                Text(Copy.appName, style = Theme.bigTitle, color = Theme.ink)
                Text(Copy.text("app.tagline"), style = Theme.body, color = Theme.muted)
            }
            Box(Modifier.padding(horizontal = 16.dp, vertical = 8.dp)) {
                Segmented(AuthMode.entries.map { it to it.title }, mode) { mode = it; error = null }
            }
            FormSection(footer = {
                if (mode == AuthMode.SignUp) {
                    Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                        Text(Copy.text("ui.at.least.8.characters"), style = Theme.subtitle, color = Theme.muted)
                        if (usernameOnly) {
                            Text(Copy.text("ui.no.email.means.no.password"), style = Theme.subtitle, color = Theme.accent)
                        }
                    }
                } else {
                    Text(Copy.text("ui.forgot.password"), style = Theme.action, color = Theme.accent, modifier = Modifier.padding(top = 4.dp).clickable { forgot = true })
                }
            }) {
                FormField(email, { email = it }, Copy.text("ui.email.or.username"), KeyboardOptions(keyboardType = KeyboardType.Email, capitalization = KeyboardCapitalization.None, autoCorrectEnabled = false))
                Hairline()
                FormField(password, { password = it }, "Password", KeyboardOptions(keyboardType = KeyboardType.Password), password = true)
                if (mode == AuthMode.SignUp) {
                    Hairline()
                    FormField(householdName, { householdName = it }, Copy.text("ui.household.name.optional"))
                }
            }
            if (mode == AuthMode.SignUp) {
                Column(
                    Modifier.padding(horizontal = 16.dp, vertical = 4.dp).fillMaxWidth(),
                    verticalArrangement = Arrangement.spacedBy(4.dp),
                ) {
                    Text(
                        Copy.text("privacy.signup.note"), style = Theme.subtitle, color = Theme.ink,
                        modifier = Modifier.fillMaxWidth().background(Theme.aubergineTint, RoundedCornerShape(12.dp)).padding(12.dp),
                    )
                    AgreeCheckbox(agreedPrivacy, { agreedPrivacy = it }, Copy.text("privacy.signup.checkbox"))
                    Text(
                        Copy.text("privacy.link"), style = Theme.action, color = Theme.accent,
                        modifier = Modifier.heightIn(min = 44.dp).clickable { showPrivacy = true }.padding(vertical = 10.dp),
                    )
                    if (!agreedPrivacy) Text(Copy.text("privacy.signup.needed"), style = Theme.subtitle, color = Theme.muted)
                }
            }
            if (showPrivacy) PrivacyPolicyDialog { showPrivacy = false }
            error?.let { Box(Modifier.padding(horizontal = 16.dp, vertical = 8.dp)) { ErrorBanner(it) } }
            Box(Modifier.padding(horizontal = 16.dp, vertical = 8.dp)) {
                Box(
                    Modifier.fillMaxWidth().heightIn(min = 44.dp).clip(RoundedCornerShape(10.dp))
                        .background(if (canSubmit) Theme.accent else Theme.accent.copy(alpha = 0.4f))
                        .clickable(enabled = canSubmit) { submit() },
                    contentAlignment = Alignment.Center,
                ) {
                    if (busy) CircularProgressIndicator(color = Color.White, strokeWidth = 2.dp, modifier = Modifier.size(20.dp))
                    else Text(mode.title, style = Theme.action, color = Color.White)
                }
            }
            if (session.canContinueAsGuest && !isSheet) {
                Column(Modifier.padding(horizontal = 16.dp, vertical = 8.dp)) {
                    Box(
                        Modifier.fillMaxWidth().heightIn(min = 44.dp).clip(RoundedCornerShape(10.dp)).background(Theme.surface)
                            .clickable { session.continueAsGuest() },
                        contentAlignment = Alignment.Center,
                    ) { Text(Copy.text("ui.continue.as.guest"), style = Theme.action, color = Theme.accent) }
                    Text(
                        Copy.text("ui.everything.works.as.a.guest"),
                        style = Theme.subtitle, color = Theme.muted, modifier = Modifier.padding(horizontal = 16.dp, vertical = 6.dp),
                    )
                }
            }
        }
    }
    if (forgot) Sheet(onDismiss = { forgot = false }) { ForgotPasswordView(email) }
}

/** Asks the server to email a reset link. The link opens the website to set a new password. */
@Composable
fun ForgotPasswordView(initialEmail: String) {
    val scope = rememberCoroutineScope()
    var email by remember { mutableStateOf(initialEmail) }
    var busy by remember { mutableStateOf(false) }
    var sent by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    val canSend = !busy && email.contains("@")

    Column(Modifier.fillMaxSize().background(Theme.bg)) {
        SheetBar(title = Copy.text("ui.reset.password"), cancel = if (sent) "Done" else "Cancel")
        Column(Modifier.verticalScroll(rememberScrollState())) {
            if (sent) {
                FormSection {
                    Column(Modifier.padding(vertical = 12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            Icon(Icons.Outlined.Email, null, tint = Theme.accent)
                            Text(Copy.text("ui.check.your.email"), style = Theme.mealName, color = Theme.ink)
                        }
                        Text(
                            "If $email has an account with a verified email, a reset link is on its way. It works once, for 1 hour. After you set a new password, come back here and sign in.",
                            style = Theme.body, color = Theme.muted,
                        )
                    }
                }
            } else {
                FormSection(footer = { Text(Copy.text("ui.well.email.you.a.link")) }) {
                    FormField(email, { email = it }, "Email", KeyboardOptions(keyboardType = KeyboardType.Email, autoCorrectEnabled = false))
                }
                error?.let { Box(Modifier.padding(horizontal = 16.dp, vertical = 8.dp)) { ErrorBanner(it) } }
                Box(Modifier.padding(horizontal = 16.dp, vertical = 8.dp)) {
                    Box(
                        Modifier.fillMaxWidth().heightIn(min = 44.dp).clip(RoundedCornerShape(10.dp))
                            .background(if (canSend) Theme.accent else Theme.accent.copy(alpha = 0.4f))
                            .clickable(enabled = canSend) {
                                busy = true
                                scope.launch {
                                    try {
                                        AuthApi.forgotPassword(email.trim())
                                        sent = true
                                        error = null
                                    } catch (e: Throwable) {
                                        error = Api.message(e)
                                    } finally {
                                        busy = false
                                    }
                                }
                            },
                        contentAlignment = Alignment.Center,
                    ) {
                        if (busy) CircularProgressIndicator(color = Color.White, strokeWidth = 2.dp, modifier = Modifier.size(20.dp))
                        else Text(Copy.text("ui.send.reset.link"), style = Theme.action, color = Color.White)
                    }
                }
            }
        }
    }
}
