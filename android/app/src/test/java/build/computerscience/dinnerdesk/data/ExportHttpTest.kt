package build.computerscience.dinnerdesk.data

import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.junit.Assert.*
import org.junit.Test

class ExportHttpTest {
    @Test fun exportDoesNotRequestTheRedirectDestination() {
        MockWebServer().use { server ->
            server.enqueue(MockResponse().setResponseCode(302).setHeader("Location", "/elsewhere"))
            server.enqueue(MockResponse().setBody("private export"))
            server.start()
            val client = exportClient(OkHttpClient())
            client.newCall(Request.Builder().url(server.url("/api/household/export")).build()).execute().use {
                assertEquals(302, it.code)
            }
            assertEquals(1, server.requestCount)
            assertFalse(client.followSslRedirects)
        }
    }
}
