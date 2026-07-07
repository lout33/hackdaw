# Examples

`timeline.json` is plain JSON and the renderers are ~80-line scripts — that's
the design. When the built-in mix chain isn't what you want, don't fight a
plugin API: copy a renderer, change the chain, re-run.

- **`mix_styles.py`** — renders the same timeline through three different
  master-bus styles (`ed` / `big` / `close`), loudness-matched so you can A/B
  them honestly. Start here to build your own mix presets:

  ```bash
  .venv/bin/python examples/mix_styles.py my_song
  ```

The pattern for your own scripts: load `timeline.json`, read the stems it
references, place each clip at `start` (respecting `trim_start`/`trim_end`,
`gain_db`, `track_gains`, `muted_tracks`), then process the buses however you
like with [pedalboard](https://github.com/spotify/pedalboard). `timeline.py`
is the reference implementation.
