package build.computerscience.dinnerdesk.data

import java.io.IOException
import kotlinx.coroutines.runBlocking
import okhttp3.Protocol
import okhttp3.Request
import okhttp3.Response
import okhttp3.ResponseBody
import okio.Buffer
import okio.ForwardingSource
import okio.buffer
import org.junit.Assert.*
import org.junit.Test

class ApiResponseTest {
    @Test fun streamedBodiesAreReadOffTheCallingThreadAndClosed() = runBlocking {
        val caller = Thread.currentThread()
        var reading: Thread? = null
        var closed = false
        val source = object : ForwardingSource(Buffer().writeUtf8("private export")) {
            override fun read(sink: Buffer, byteCount: Long): Long {
                reading = Thread.currentThread()
                return super.read(sink, byteCount)
            }
            override fun close() { closed = true; super.close() }
        }.buffer()
        val body = object : ResponseBody() {
            override fun contentType() = null
            override fun contentLength() = -1L
            override fun source() = source
        }
        val response = Response.Builder().request(Request.Builder().url("https://example.test").build())
            .protocol(Protocol.HTTP_1_1).code(200).message("OK").body(body).build()
        assertEquals("private export", consumeResponse(response) { it.body!!.string() })
        assertNotSame(caller, reading)
        assertTrue(closed)
    }

    @Test fun authErrorsPreferTheExplanationOverTheCode() {
        assertEquals("Use a different address.", ApiError(400, """{"detail":"email_taken","message":"Use a different address."}""").message)
        assertEquals("Choose a new owner first.", ApiError(409, """{"detail":"successor_required","message":"Choose a new owner first."}""").message)
        assertEquals("Check your email and password.", ApiError(401, """{"detail":"invalid_credentials","message":"Check your email and password."}""").message)
        assertEquals("Try another name.", ApiError(400, """{"detail":"Try another name."}""").message)
        assertFalse(ApiError(500, """{"message":"private server details"}""").message.contains("private"))
    }
}
