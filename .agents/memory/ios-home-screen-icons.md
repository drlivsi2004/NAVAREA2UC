---
name: iOS Home Screen icons
description: Reliable icon selection when adding the NAVAREA2UC web app to an iPhone Home Screen
---

iOS Safari uses a dedicated `apple-touch-icon` asset for “Add to Home Screen”; a normal favicon or Windows `.ico` is not a reliable substitute. If Safari keeps showing an earlier icon, change the `apple-touch-icon` URL as well as replacing the image so the browser fetches a new resource.

**Why:** The iPhone Home Screen flow can retain the previous icon even after the image at the original URL is replaced.

**How to apply:** Provide a square PNG at the iOS-recommended size, link it with `rel="apple-touch-icon"`, and use a new filename when changing the icon.