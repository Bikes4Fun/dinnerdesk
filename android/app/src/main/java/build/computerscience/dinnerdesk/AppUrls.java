package build.computerscience.dinnerdesk;

import java.net.URI;

/** Navigation stays within the configured HTTPS API origin, including debug servers. */
public final class AppUrls {
    public static boolean isInternal(String value) {
        return isInternal(value, BuildConfig.APP_ORIGIN);
    }

    static boolean isInternal(String value, String configuredOrigin) {
        try {
            URI uri = URI.create(value);
            URI origin = URI.create(configuredOrigin);
            return "https".equalsIgnoreCase(uri.getScheme())
                && "https".equalsIgnoreCase(origin.getScheme())
                && origin.getHost() != null && origin.getHost().equalsIgnoreCase(uri.getHost())
                && origin.getUserInfo() == null && uri.getUserInfo() == null
                && port(uri) == port(origin);
        } catch (IllegalArgumentException | NullPointerException error) { return false; }
    }

    private static int port(URI uri) { return uri.getPort() == -1 ? 443 : uri.getPort(); }

    public static boolean canOpenExternal(String value) {
        try {
            String scheme = URI.create(value).getScheme();
            return "https".equalsIgnoreCase(scheme) || "http".equalsIgnoreCase(scheme)
                || "mailto".equalsIgnoreCase(scheme) || "tel".equalsIgnoreCase(scheme);
        } catch (IllegalArgumentException | NullPointerException error) { return false; }
    }
}
