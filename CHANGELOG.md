# Changelog


## [Unreleased]

### Features

- Modified the Sonify Data plugin to send audio data from the server to the client for playback in the browser.
- The Python backend now generates a `.wav` notification in memory using strauss, encodes it in base64, and sends it to the frontend.
- The Vue.js frontend now decodes the base64 audio data and plays it using the Web Audio API.
