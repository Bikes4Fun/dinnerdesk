package build.computerscience.dinnerdesk;

import org.junit.Test;
import static org.junit.Assert.*;

public class AppUrlsTest {
    @Test public void routesStayInsideTheExactHttpsOrigin() {
        assertTrue(AppUrls.isInternal("https://dinnerdesk.computerscience.build/recipes/14803", "https://dinnerdesk.computerscience.build"));
        assertTrue(AppUrls.isInternal("https://dinnerdesk.computerscience.build:443/api/household/export", "https://dinnerdesk.computerscience.build"));
        for (String url : new String[] {
            "http://dinnerdesk.computerscience.build/", "https://dinnerdesk.computerscience.build.evil.example/",
            "https://dinnerdesk.computerscience.build@evil.example/", "https://evil@dinnerdesk.computerscience.build/",
            "https://dinnerdesk.computerscience.build:8443/", "file:///etc/passwd", "javascript:alert(1)",
            "intent://example/#Intent;scheme=https;end", "not a url"
        }) assertFalse(url, AppUrls.isInternal(url, "https://dinnerdesk.computerscience.build"));
    }
    @Test public void publicPolicyUsesTheBuildOrigin() {
        assertTrue(AppUrls.isInternal(BuildConfig.APP_ORIGIN + "/recipes/1"));
    }
    @Test public void usesConfiguredDebugHostAndPort() {
        String origin = "https://branch.example:8443";
        assertTrue(AppUrls.isInternal("https://branch.example:8443/recipes/1", origin));
        assertFalse(AppUrls.isInternal("https://branch.example/recipes/1", origin));
        assertFalse(AppUrls.isInternal("https://dinnerdesk.computerscience.build/", origin));
        assertFalse(AppUrls.isInternal("https://evil@branch.example:8443/", origin));
        assertFalse(AppUrls.isInternal("https://branch.example.evil:8443/", origin));
        assertTrue(AppUrls.isInternal("https://branch.example:443/", "https://branch.example"));
        assertFalse(AppUrls.isInternal("http://branch.example/", "http://branch.example"));
        assertFalse(AppUrls.isInternal("https://branch.example/", "not an origin"));
    }
    @Test public void externalLinksNeverLaunchFileOrScriptSchemes() {
        assertTrue(AppUrls.canOpenExternal("mailto:support@example.com"));
        assertTrue(AppUrls.canOpenExternal("https://example.com/privacy"));
        assertFalse(AppUrls.canOpenExternal("content://private/file"));
        assertFalse(AppUrls.canOpenExternal("javascript:alert(1)"));
        assertFalse(AppUrls.canOpenExternal("intent://arbitrary"));
    }
}
