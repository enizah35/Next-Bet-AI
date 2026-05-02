# Mobile app

This frontend is now installable as a PWA and ready to be wrapped with Capacitor for Android and iOS.

## PWA

Run a production build:

```bash
npm run build
npm run start
```

Then open the site from a mobile browser. Android Chrome and desktop Chromium expose an install action when the manifest and service worker are detected. iOS Safari can install it with "Add to Home Screen".

Included mobile assets:

- `public/manifest.webmanifest`
- `public/sw.js`
- `public/offline.html`
- `public/icons/*.png`

## Native shell with Capacitor

The app uses Next.js server rendering and Supabase auth, so the native shell should point at the deployed web URL instead of a static export.

Set the deployed URL before syncing native projects:

```bash
$env:NEXT_PUBLIC_APP_URL="https://your-domain.example"
npm run mobile:add:android
npm run mobile:add:ios
npm run mobile:sync
```

Open the native projects:

```bash
npm run mobile:open:android
npm run mobile:open:ios
```

Android can be built from Android Studio. iOS requires macOS and Xcode.
