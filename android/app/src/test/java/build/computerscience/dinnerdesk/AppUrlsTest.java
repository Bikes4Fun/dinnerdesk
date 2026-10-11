package build.computerscience.dinnerdesk;

import org.junit.Test;
import static org.junit.Assert.*;

public class AppUrlsTest {
    @Test public void routesStayInsideTheExactHttpsOrigin() {
        assertTrue(AppUrls.isInternal("https://dinnerdesk.computerscience.build/recipes/14803"));
        assertTrue(AppUrls.isInternal("https://dinnerdesk.computerscience.build:443/api/household/export"));
        for (String url : new String[] {
            "http://dinnerdesk.computerscience.build/", "https://dinnerdesk.computerscience.build.evil.example/",
            "https://dinnerdesk.computerscience.build@evil.example/", "https://evil@dinnerdesk.computerscience.build/",
            "https://dinnerdesk.computerscience.build:8443/", "file:///etc/passwd", "javascript:alert(1)",
            "intent://example/#Intent;scheme=https;end", "not a url"
        }) assertFalse(url, AppUrls.isInternal(url));
    }
    @Test public void externalLinksNeverLaunchFileOrScriptSchemes() {
        assertTrue(AppUrls.canOpenExternal("mailto:support@example.com"));
        assertTrue(AppUrls.canOpenExternal("https://example.com/privacy"));
        assertFalse(AppUrls.canOpenExternal("content://private/file"));
        assertFalse(AppUrls.canOpenExternal("javascript:alert(1)"));
        assertFalse(AppUrls.canOpenExternal("intent://arbitrary"));
    }
}
