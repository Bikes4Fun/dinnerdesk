package build.computerscience.dinnerdesk

import android.app.Application
import android.graphics.Color
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.SystemBarStyle
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.runtime.CompositionLocalProvider
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.compose.viewModel
import build.computerscience.dinnerdesk.data.Api
import build.computerscience.dinnerdesk.data.Copy
import build.computerscience.dinnerdesk.data.Session
import build.computerscience.dinnerdesk.data.Store
import build.computerscience.dinnerdesk.ui.AuthGate
import build.computerscience.dinnerdesk.ui.ContentView
import build.computerscience.dinnerdesk.ui.DinnerdeskTheme
import build.computerscience.dinnerdesk.ui.LocalSession
import build.computerscience.dinnerdesk.ui.LocalStore

class DinnerdeskApp : Application() {
    override fun onCreate() {
        super.onCreate()
        Api.init(this)
        Copy.load(this)
    }
}

/** Survives rotation: the signed-in session and the household's data. */
class AppModel(app: Application) : AndroidViewModel(app) {
    val session = Session()
    val store = Store(viewModelScope, app)
}

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge(
            statusBarStyle = SystemBarStyle.light(Color.TRANSPARENT, Color.TRANSPARENT),
            navigationBarStyle = SystemBarStyle.light(Color.TRANSPARENT, Color.TRANSPARENT),
        )
        setContent {
            val model: AppModel = viewModel()
            DinnerdeskTheme {
                CompositionLocalProvider(LocalSession provides model.session, LocalStore provides model.store) {
                    AuthGate { ContentView() }
                }
            }
        }
    }
}
