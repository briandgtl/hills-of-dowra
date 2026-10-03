# Hills of Dowra

A sheep-herding game set in the Cavan hills of Ireland. Your flock has slipped the gate and scattered across the hills: bring them home before the sun goes down, and keep them happy once they're back.

The whole game is one file, `Hills of Dowra.html`. The terrain, trees, walls, ruins, graveyards, sheep, shepherd and weather are all generated in code.

## Run it

It loads three.js from a CDN, so you need a connection. Serve the folder and open it in a current browser:

```bash
python3 -m http.server 8000
```

Then open `http://localhost:8000/Hills%20of%20Dowra.html`.

It uses WebGPU where the browser has it and falls back to WebGL 2 otherwise. Add `?webgl` to the URL to force the fallback.

## Play offline

```bash
python3 tools/make-offline.py
```

This writes `Hills of Dowra (offline).html`: the same game as one file of about 6 MB, with three.js, the other libraries and the fonts embedded. Open it in the browser; it needs no server and no connection. The first build downloads the libraries from jsDelivr and Google Fonts and keeps them in `tools/cache/`, so later builds are offline too. Rebuild it after changing the game. The generated file isn't committed.

## Controls

| | |
|---|---|
| WASD | walk |
| Space | crook |
| F | farm shop |
| C | cottage |
| Esc | pause |
| Scroll | zoom |
| Drag | walk on touch |

## Built with

- [three.js](https://threejs.org) (WebGPU build, node materials in TSL), loaded from jsDelivr through an import map
- [three-mesh-bvh](https://github.com/gkjohnson/three-mesh-bvh) and [meshoptimizer](https://github.com/zeux/meshoptimizer)

Progress is saved in the browser's local storage.
