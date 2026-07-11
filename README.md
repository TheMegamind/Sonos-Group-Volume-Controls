# Sonos Group Volume

A custom Home Assistant integration that synthesizes a **group volume** control
for each Sonos speaker — a `number` entity that reflects and controls the
average volume of whatever Sonos group that speaker currently belongs to.

Companion to core Home Assistant's `sonos` integration. Does not replace or
modify it.

## What it does

For every Sonos `media_player` entity in your system, this integration adds a
matching `number` entity (nested under that speaker's existing device card):

- **Grouped speakers:** the number entity shows and controls the *average*
  volume across all speakers currently in that group.
- **Solo speakers** (not grouped, or a group of one): the number entity
  mirrors that speaker's individual volume 1:1.
- **Adjusting the slider** on a grouped speaker's entity proportionally
  scales every member's individual volume up or down, preserving their
  relative balance — the same behavior as Sonos's own group volume fader.
- Entities update live as speakers join/leave groups or as any member's
  volume changes, from any source (Sonos app, physical controls, other HA
  automations).
- Group volume is **truncated**, not rounded, to match Sonos's own display
  convention (e.g. 16.9% displays as `16`, not `17`).

## Requirements

- Home Assistant with the core `sonos` integration already set up and
  working.
- Python 3.14+ (matches current HA core requirements).

## Manual installation

This integration isn't distributed through any store yet — install it by
copying the code directly into your Home Assistant config.

1. Copy the `custom_components/sonos_group_volume/` folder from this repo
   into your Home Assistant config directory, so you end up with:
   ```
   <config>/custom_components/sonos_group_volume/
     __init__.py
     manifest.json
     config_flow.py
     const.py
     number.py
     strings.json
     translations/en.json
   ```
2. Restart Home Assistant (a full restart — not just a config reload —
   is required for HA to discover a newly added custom integration).
3. Go to **Settings → Devices & Services → Add Integration**, search for
   **Sonos Group Volume**, and complete the setup (no configuration
   options — it auto-discovers your existing Sonos speakers).
4. A `number.<speaker>_group_volume` entity should appear for each Sonos
   speaker, nested under that speaker's device card.

To update after pulling new changes, replace the copied folder with the
latest version and do another full restart.

## How it works (brief)

- Group membership is read from each Sonos player's `group_members`
  attribute at evaluation time — never cached across calls.
- The integration listens for state changes on every entity in a group (via
  `homeassistant.helpers.event.async_track_state_change_event`) and
  recomputes/publishes the group volume whenever any member's state changes.
- Adjusting a group volume entity computes a proportional scale factor from
  the current group average to the requested target, then applies it to
  each member individually via `media_player.volume_set`. If every member
  is at 0% (scale factor undefined), it falls back to setting every member
  directly to the requested value instead.

## Known limitations

- Proportional scaling can clamp at 0% or 100% for individual members,
  meaning the resulting group average may not land exactly on the
  requested target in edge cases. This matches Sonos's own group-fader
  behavior and is inherent to bounded proportional scaling, not a bug.
- No configuration options yet — all Sonos players are always included.

## Development status

Actively under development. Test suite lives in
`tests/components/sonos_group_volume/` (`pytest-homeassistant-custom-component`
harness). Run tests before committing changes:

```bash
source .venv/bin/activate
pytest tests/components/sonos_group_volume/
```

## License

TBD.
