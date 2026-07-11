# Sonos Group Volume

A custom Home Assistant integration that creates a **group volume** control entity for each Sonos speaker (or speaker pair) within a given system.

Group Volume, as defined by Sonos and incorporated within the Sonos Control API, is the *average* volume across all speakers currently in that group.

Note: This integration is a companion to Home Assistant's own `Sonos` integration and does not replace or modify it. Although group volume is available in the `SoCo` library that Home Assistant's `sonos` integration wraps, core does not expose it as an entity, despite efforts to add it. Even so, the entities would likely be available only to group coordinators due to established HA practice.

## What it does

For every Sonos `media_player` entity in your system, this integration adds a matching `number` entity that is neatly displayed within that speaker's existing device card:

- **Grouped speakers:** the number entity shows and controls the *average* volume across all speakers currently in that group.
- **Ungrouped speakers**: the number entity mirrors that speaker's individual volume 1:1.
- **Adjusting the slider** on a grouped speaker's entity proportionally
  scales every member's individual volume up or down, preserving their
  relative balance.
- Entities update live as speakers join/leave groups or as any member's
  volume changes, from any source (Sonos app, physical controls, other HA
  automations).
- Group volume is **truncated**, not rounded, to match Sonos's own display convention (e.g., 16.9% displays as `16`, not `17`).

## Requirements

- Home Assistant with the core `sonos` integration already set up and
  working.
- Python 3.14+

## Installation

1. In Home Assistant: **HACS → ⋮ (top right) → Custom repositories**, add
   `https://github.com/TheMegamind/ha-sonos-group-volume`, set type to
   **Integration**, and click **Add**. Then find it in HACS and click
   **Download**.
2. Restart Home Assistant.
3. Go to **Settings → Devices & Services → Add Integration**, search for
   **Sonos Group Volume**, and complete the setup (no configuration
   options — it auto-discovers your existing Sonos speakers).
4. A `number.<speaker>_group_volume` entity will appear for each Sonos
   speaker, nested under that speaker's device card.

## How it works

- Group membership is read from each Sonos player's `group_members`
  attribute at evaluation time — never cached across calls.
- The integration listens for state changes on every entity in a group and updates the group volume value whenever any member's state changes.
- Adjusting a group volume entity computes a proportional scale factor from the current group average to the requested target, then applies it to each member individually via `media_player.volume_set`. If every member is at 0% (scale factor undefined), it falls back to setting every member directly to the requested value instead.

## License

MIT — see [LICENSE](LICENSE) for details.
