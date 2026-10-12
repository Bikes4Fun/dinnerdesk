# Dinnerdesk for Android

Issue [#112](https://github.com/Bikes4Fun/dinnerdesk/issues/112), branch `issue-112-android-google-play`.

This Android app presents Dinnerdesk's mobile website in a restricted WebView. The server supplies meal planning, groceries, prep, preferences, and recipe editing, so web changes reach both platforms. Native Android code provides back navigation, keyboard/system-bar insets, connection recovery, a system photo picker, a native grocery share sheet, and an authenticated JSON data export saved through the system document picker. It does not request storage, camera, location, or microphone permissions. External links open in the user's browser or matching app. Only the Dinnerdesk HTTPS origin stays inside the app.

## Build

Install JDK 17 and the Android SDK (accept its license), including platform 36 and build-tools 36.0.0. Set `ANDROID_HOME` to the SDK or create an ignored `local.properties` with `sdk.dir=...`.

```sh
cd android
./gradlew testDebugUnitTest lintDebug assembleDebug bundleRelease
```

Outputs: `app/build/outputs/apk/debug/app-debug.apk` and `app/build/outputs/bundle/release/app-release.aab`. The debug app uses `build.computerscience.dinnerdesk.debug`; release uses `build.computerscience.dinnerdesk`. Check availability of the release identifier in Play Console before registering it. Release bundles are unsigned until the owner configures an upload key.

For a signed release, set `DINNERDESK_UPLOAD_KEYSTORE` (absolute path), `DINNERDESK_UPLOAD_STORE_PASSWORD`, `DINNERDESK_UPLOAD_KEY_ALIAS`, and `DINNERDESK_UPLOAD_KEY_PASSWORD` in the local environment, then run `./gradlew bundleRelease`. Keep keys/passwords out of Git and use Play App Signing. Increment `versionCode` for every uploaded release.

## Google Play checklist

- Owner creates/selects the Play Console app and confirms the package identifier, upload key, account verification and any account-specific testing requirements.
- Test first in the internal track. This is an initial Android implementation; device acceptance and Google Play review remain required.
- Target SDK is 36. Confirm the [current target SDK policy](https://developer.android.com/google/play/requirements/target-sdk) when uploading.
- Review the live [privacy policy](https://dinnerdesk.computerscience.build/privacy) and [support page](https://dinnerdesk.computerscience.build/support). Complete Data safety from actual server collection/retention and third-party integrations. The app sends account and kitchen information to Dinnerdesk over HTTPS; do not claim it collects no data.
- Provide store text, Android screenshots, 512px store icon and feature graphic, content rating, audience declarations and app access instructions using a dedicated review account. Confirm account/data deletion satisfies Play requirements. Do not include personal tester information in the listing.
- Confirm the mobile site meets Play's functionality and quality requirements. A working wrapper alone does not guarantee store approval.
- Merge/deploy PR #99 before testing native data export; its endpoint returns 404 on older servers. Merge/deploy PR #111 for the shared web TestFlight fixes.

## Device acceptance

Test an Android phone on API 26 and API 36, including gesture and three-button navigation and large fonts:

1. Sign in, relaunch and confirm the kitchen session persists. Sign out and confirm authenticated actions stop working.
2. Create and edit a plan, complete groceries, check prep, change filters and visit a recipe. Back should navigate the site before leaving the app.
3. As an admin, select JPEG/PNG/WebP with the system picker, cancel, upload and revisit the recipe. Rotate while choosing a photo and retry if the system recreates the activity. Unsupported files should be rejected.
4. Export household data using the native menu, cancel the destination picker, then save and inspect a JSON file. Confirm expired sessions and an older server show useful errors. Rotation while saving may require retry because exported private data is kept only in memory.
5. Follow external links and verify they leave the app. Check the privacy/support actions. No file URLs, JavaScript URLs or intent URLs should open inside the app.
6. Disable networking, retry, restore networking, and verify recovery without losing server data. Test keyboard overlap, safe areas and accessibility labels.
7. Test the signed internal-track bundle installed through Play, not only the debug APK.

The app deliberately keeps no JavaScript-to-native bridge. The system grants access only to the photo/document selected by the user. Export requests send cookies only to the fixed Dinnerdesk endpoint and do not follow redirects.
