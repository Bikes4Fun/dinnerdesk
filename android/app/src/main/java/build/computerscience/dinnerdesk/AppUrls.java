package build.computerscience.dinnerdesk;

import java.net.URI;

/** A fixed HTTPS origin: navigation and authenticated requests use the same policy. */
final class AppUrls {
    static boolean isInternal(String value) {
        try {
            URI uri = URI.create(value);
            return "https".equalsIgnoreCase(uri.getScheme())
                && "dinnerdesk.computerscience.build".equalsIgnoreCase(uri.getHost())
                && uri.getUserInfo() == null && (uri.getPort() == -1 || uri.getPort() == 443);
        } catch (IllegalArgumentException | NullPointerException error) { return false; }
    }

    static boolean canOpenExternal(String value) {
        try {
            String scheme = URI.create(value).getScheme();
            return "https".equalsIgnoreCase(scheme) || "http".equalsIgnoreCase(scheme)
                || "mailto".equalsIgnoreCase(scheme) || "tel".equalsIgnoreCase(scheme);
        } catch (IllegalArgumentException | NullPointerException error) { return false; }
    }
}
