package build.computerscience.dinnerdesk;

import android.annotation.SuppressLint;
import android.content.Intent;
import android.graphics.Color;
import android.net.Uri;
import android.net.http.SslError;
import android.os.Bundle;
import android.webkit.*;
import android.widget.*;
import android.view.View;
import androidx.activity.ComponentActivity;
import androidx.activity.OnBackPressedCallback;
import androidx.activity.result.ActivityResultLauncher;
import androidx.activity.result.contract.ActivityResultContracts;
import androidx.core.graphics.Insets;
import androidx.core.view.ViewCompat;
import androidx.core.view.WindowCompat;
import androidx.core.view.WindowInsetsCompat;
import java.io.*;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.time.LocalDate;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/** Native lifecycle, navigation, photo selection and authenticated data export. */
public final class MainActivity extends ComponentActivity {
    private WebView web;
    private FrameLayout content;
    private LinearLayout errorPanel;
    private ProgressBar progress;
    private String lastUrl = BuildConfig.APP_ORIGIN + "/";
    private ValueCallback<Uri[]> photoCallback;
    private byte[] pendingDownload;
    private boolean downloading;
    private boolean sharing;
    private final ExecutorService worker = Executors.newSingleThreadExecutor();
    private final ActivityResultLauncher<Intent> photos = registerForActivityResult(
        new ActivityResultContracts.StartActivityForResult(), result -> {
            ValueCallback<Uri[]> callback = photoCallback;
            photoCallback = null;
            if (callback == null) { toast(R.string.photo_picker_lost); return; }
            Uri uri = result.getResultCode() == RESULT_OK && result.getData() != null
                ? result.getData().getData() : null;
            if (uri != null && "content".equals(uri.getScheme())) {
                String type = getContentResolver().getType(uri);
                if ("image/jpeg".equals(type) || "image/png".equals(type) || "image/webp".equals(type)) {
                    callback.onReceiveValue(new Uri[]{uri}); return;
                }
                toast(R.string.choose_photo);
            }
            callback.onReceiveValue(null);
        });
    private final ActivityResultLauncher<String> saveFile = registerForActivityResult(
        new ActivityResultContracts.CreateDocument("application/json"), uri -> {
            byte[] bytes = pendingDownload;
            pendingDownload = null;
            downloading = false;
            if (uri == null) return;
            if (bytes == null) { toast(R.string.download_failed); return; }
            worker.execute(() -> {
                try (OutputStream output = getContentResolver().openOutputStream(uri, "w")) {
                    if (output == null) throw new IOException();
                    output.write(bytes);
                    runOnUiThread(() -> toast(R.string.saved));
                } catch (IOException error) { runOnUiThread(() -> toast(R.string.save_failed)); }
            });
        });

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        WindowCompat.setDecorFitsSystemWindows(getWindow(), false);
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setBackgroundColor(Color.rgb(255, 252, 245));
        ViewCompat.setOnApplyWindowInsetsListener(root, (view, insets) -> {
            Insets safe = insets.getInsets(WindowInsetsCompat.Type.systemBars() | WindowInsetsCompat.Type.displayCutout());
            Insets keyboard = insets.getInsets(WindowInsetsCompat.Type.ime());
            view.setPadding(safe.left, safe.top, safe.right, Math.max(safe.bottom, keyboard.bottom));
            return insets;
        });
        LinearLayout toolbar = new LinearLayout(this);
        toolbar.setGravity(android.view.Gravity.CENTER_VERTICAL);
        TextView title = new TextView(this);
        title.setText(R.string.app_name); title.setTextSize(20); title.setPadding(dp(16), 0, 0, 0);
        toolbar.addView(title, new LinearLayout.LayoutParams(0, dp(48), 1));
        Button menu = new Button(this); menu.setText("⋮"); menu.setContentDescription(getString(R.string.app_menu));
        menu.setOnClickListener(this::showMenu);
        toolbar.addView(menu, new LinearLayout.LayoutParams(dp(56), dp(48)));
        root.addView(toolbar);
        content = new FrameLayout(this);
        root.addView(content, new LinearLayout.LayoutParams(-1, 0, 1));
        setContentView(root);
        createWebView();
        if (state == null || web.restoreState(state) == null) web.loadUrl(lastUrl);
        getOnBackPressedDispatcher().addCallback(this, new OnBackPressedCallback(true) {
            @Override public void handleOnBackPressed() {
                if (web.canGoBack()) web.goBack();
                else { setEnabled(false); getOnBackPressedDispatcher().onBackPressed(); }
            }
        });
    }
    @SuppressLint("SetJavaScriptEnabled") private void createWebView() {
        web = new WebView(this);
        WebSettings settings = web.getSettings();
        settings.setJavaScriptEnabled(true); settings.setDomStorageEnabled(true);
        settings.setAllowFileAccess(false); settings.setAllowContentAccess(false);
        settings.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        settings.setSafeBrowsingEnabled(true);
        CookieManager.getInstance().setAcceptCookie(true);
        CookieManager.getInstance().setAcceptThirdPartyCookies(web, false);
        WebView.setWebContentsDebuggingEnabled(BuildConfig.DEBUG);
        web.setWebViewClient(new WebViewClient() {
            @Override public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                String url = request.getUrl().toString();
                if (AppUrls.isInternal(url)) return false;
                if (request.isForMainFrame() && request.hasGesture()) openExternal(url);
                return true;
            }
            @Override public void onPageStarted(WebView view, String url, android.graphics.Bitmap icon) {
                if (AppUrls.isInternal(url)) lastUrl = url;
                progress.setVisibility(View.VISIBLE); errorPanel.setVisibility(View.GONE);
            }
            @Override public void onPageFinished(WebView view, String url) { progress.setVisibility(View.GONE); }
            @Override public void onReceivedError(WebView view, WebResourceRequest request, WebResourceError error) {
                if (request.isForMainFrame()) showError();
            }
            @Override public void onReceivedHttpError(WebView view, WebResourceRequest request, WebResourceResponse response) {
                if (request.isForMainFrame() && response.getStatusCode() >= 400) showError();
            }
            @Override public void onReceivedSslError(WebView view, SslErrorHandler handler, SslError error) {
                handler.cancel(); showError();
            }
            @Override public boolean onRenderProcessGone(WebView view, RenderProcessGoneDetail detail) {
                content.removeAllViews(); view.destroy(); createWebView(); showError(); return true;
            }
        });
        web.setWebChromeClient(new WebChromeClient() {
            @Override public boolean onShowFileChooser(WebView view, ValueCallback<Uri[]> callback, FileChooserParams params) {
                if (photoCallback != null) photoCallback.onReceiveValue(null);
                photoCallback = callback;
                Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE)
                    .setType("image/*").putExtra(Intent.EXTRA_MIME_TYPES, new String[]{"image/jpeg", "image/png", "image/webp"});
                try { photos.launch(intent); }
                catch (android.content.ActivityNotFoundException error) { photoCallback = null; callback.onReceiveValue(null); toast(R.string.picker_unavailable); }
                return true;
            }
            @Override public void onPermissionRequest(PermissionRequest request) { request.deny(); }
            @Override public void onGeolocationPermissionsShowPrompt(String origin, GeolocationPermissions.Callback callback) {
                callback.invoke(origin, false, false);
            }
        });
        web.setDownloadListener((url, agent, disposition, type, length) -> {
            // Only the known household export endpoint may receive the signed-in cookie.
            if ((BuildConfig.APP_ORIGIN + "/api/household/export").equals(url)) exportData();
            else openExternal(url);
        });
        content.addView(web, new FrameLayout.LayoutParams(-1, -1));
        progress = new ProgressBar(this, null, android.R.attr.progressBarStyleHorizontal);
        content.addView(progress, new FrameLayout.LayoutParams(-1, dp(3)));
        errorPanel = new LinearLayout(this); errorPanel.setOrientation(LinearLayout.VERTICAL);
        errorPanel.setGravity(android.view.Gravity.CENTER); errorPanel.setPadding(dp(24), dp(24), dp(24), dp(24));
        errorPanel.setBackgroundColor(Color.rgb(255, 252, 245));
        TextView title = new TextView(this); title.setText(R.string.offline_title); title.setTextSize(22);
        TextView message = new TextView(this); message.setText(R.string.offline_message);
        Button retry = new Button(this); retry.setText(R.string.retry); retry.setOnClickListener(v -> web.loadUrl(lastUrl));
        errorPanel.addView(title); errorPanel.addView(message); errorPanel.addView(retry);
        errorPanel.setVisibility(View.GONE); content.addView(errorPanel, new FrameLayout.LayoutParams(-1, -1));
    }
    private void showMenu(View anchor) {
        PopupMenu menu = new PopupMenu(this, anchor);
        menu.getMenu().add(0, 1, 0, R.string.reload);
        menu.getMenu().add(0, 2, 1, R.string.export_data);
        menu.getMenu().add(0, 5, 2, R.string.share_groceries);
        menu.getMenu().add(0, 3, 2, R.string.privacy);
        menu.getMenu().add(0, 4, 3, R.string.support);
        menu.setOnMenuItemClickListener(item -> {
            switch (item.getItemId()) {
                case 1: web.loadUrl(lastUrl); break;
                case 2: exportData(); break;
                case 5: shareGroceries(); break;
                case 3: web.loadUrl(BuildConfig.APP_ORIGIN + "/privacy"); break;
                case 4: web.loadUrl(BuildConfig.APP_ORIGIN + "/support"); break;
                default: return false;
            }
            return true;
        }); menu.show();
    }
    private void exportData() {
        if (downloading) return;
        downloading = true; toast(R.string.preparing);
        String url = BuildConfig.APP_ORIGIN + "/api/household/export";
        String cookie = CookieManager.getInstance().getCookie(url);
        worker.execute(() -> {
            HttpURLConnection connection = null;
            try {
                connection = (HttpURLConnection) new URL(url).openConnection();
                connection.setInstanceFollowRedirects(false); connection.setConnectTimeout(15000); connection.setReadTimeout(30000);
                connection.setRequestProperty("Accept", "application/json");
                if (cookie != null) connection.setRequestProperty("Cookie", cookie);
                int status = connection.getResponseCode();
                if (status != 200) {
                    int message = status == 401 || status == 403 ? R.string.sign_in_again : status == 404 ? R.string.export_unavailable : R.string.download_failed;
                    runOnUiThread(() -> { downloading = false; toast(message); }); return;
                }
                ByteArrayOutputStream bytes = new ByteArrayOutputStream();
                try (InputStream input = connection.getInputStream()) {
                    byte[] buffer = new byte[8192]; int count;
                    while ((count = input.read(buffer)) != -1) {
                        if (bytes.size() + count > 20 * 1024 * 1024) throw new IOException("Export too large");
                        bytes.write(buffer, 0, count);
                    }
                }
                byte[] result = bytes.toByteArray();
                new org.json.JSONObject(new String(result, StandardCharsets.UTF_8));
                runOnUiThread(() -> {
                    if (isFinishing() || isDestroyed()) return;
                    pendingDownload = result;
                    try { saveFile.launch("dinnerdesk-data-" + LocalDate.now() + ".json"); }
                    catch (android.content.ActivityNotFoundException error) { downloading = false; pendingDownload = null; toast(R.string.picker_unavailable); }
                });
            } catch (Exception error) { runOnUiThread(() -> { downloading = false; toast(R.string.download_failed); }); }
            finally { if (connection != null) connection.disconnect(); }
        });
    }
    private void shareGroceries() {
        if (sharing) return;
        sharing = true; toast(R.string.preparing);
        String cookie = CookieManager.getInstance().getCookie(BuildConfig.APP_ORIGIN);
        worker.execute(() -> {
            try {
                org.json.JSONObject plan = readJson("/api/plans/current", cookie);
                long id = plan.getLong("id");
                org.json.JSONArray lines = readJson("/api/plans/" + id + "/grocery", cookie).getJSONArray("lines");
                StringBuilder text = new StringBuilder("Dinnerdesk grocery list\n");
                int count = 0;
                for (int i = 0; i < lines.length(); i++) {
                    org.json.JSONObject line = lines.getJSONObject(i);
                    if (line.optBoolean("checked") || line.optBoolean("never_shop") || line.optBoolean("from_pantry")) continue;
                    String name = line.optString("name", "");
                    String quantity = line.optString("quantity", "");
                    text.append("\n• ").append(quantity.isEmpty() ? "" : quantity + " ").append(name);
                    count++;
                }
                if (count == 0) { runOnUiThread(() -> { sharing = false; toast(R.string.no_groceries); }); return; }
                runOnUiThread(() -> {
                    sharing = false;
                    if (isFinishing() || isDestroyed()) return;
                    Intent intent = new Intent(Intent.ACTION_SEND).setType("text/plain")
                        .putExtra(Intent.EXTRA_TEXT, text.toString());
                    try { startActivity(Intent.createChooser(intent, getString(R.string.share_groceries))); }
                    catch (android.content.ActivityNotFoundException error) { toast(R.string.external_unavailable); }
                });
            } catch (Exception error) { runOnUiThread(() -> { sharing = false; toast(R.string.share_failed); }); }
        });
    }
    private org.json.JSONObject readJson(String path, String cookie) throws Exception {
        String url = BuildConfig.APP_ORIGIN + path;
        if (!AppUrls.isInternal(url)) throw new IOException();
        HttpURLConnection connection = (HttpURLConnection) new URL(url).openConnection();
        try {
            connection.setInstanceFollowRedirects(false);
            connection.setConnectTimeout(15000); connection.setReadTimeout(30000);
            connection.setRequestProperty("Accept", "application/json");
            if (cookie != null) connection.setRequestProperty("Cookie", cookie);
            if (connection.getResponseCode() != 200) throw new IOException();
            try (InputStream input = connection.getInputStream()) {
                ByteArrayOutputStream bytes = new ByteArrayOutputStream();
                byte[] buffer = new byte[8192]; int count;
                while ((count = input.read(buffer)) != -1) {
                    if (bytes.size() + count > 5 * 1024 * 1024) throw new IOException();
                    bytes.write(buffer, 0, count);
                }
                return new org.json.JSONObject(bytes.toString(StandardCharsets.UTF_8.name()));
            }
        } finally { connection.disconnect(); }
    }
    private void openExternal(String url) {
        if (!AppUrls.canOpenExternal(url)) return;
        try { startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(url)).addCategory(Intent.CATEGORY_BROWSABLE)); }
        catch (android.content.ActivityNotFoundException error) { toast(R.string.external_unavailable); }
    }
    private void showError() { progress.setVisibility(View.GONE); errorPanel.setVisibility(View.VISIBLE); }
    private void toast(int message) { if (!isDestroyed()) Toast.makeText(this, message, Toast.LENGTH_LONG).show(); }
    private int dp(int value) { return Math.round(value * getResources().getDisplayMetrics().density); }
    @Override protected void onSaveInstanceState(Bundle state) { web.saveState(state); super.onSaveInstanceState(state); }
    @Override protected void onResume() { super.onResume(); if (web != null) web.onResume(); }
    @Override protected void onPause() { if (web != null) web.onPause(); CookieManager.getInstance().flush(); super.onPause(); }
    @Override protected void onDestroy() {
        if (photoCallback != null) photoCallback.onReceiveValue(null);
        if (web != null) { content.removeView(web); web.destroy(); }
        pendingDownload = null; worker.shutdown(); super.onDestroy();
    }
}
