# Video (Remotion)

Source of the pitch video: `src/index.jsx` (shots, timings, transitions), `shots.js` (renders the deck slides to PNG) and `site.js` (captures the website screens).

Not in the repository: the narration audio (`public/audio/`), the rendered slide and site images (`public/`) and the rendered MP4s. Render with:

```bash
npm install
npx remotion render src/index.jsx Vigia out/vigia_orbital.mp4
```
