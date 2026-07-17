# Sonos Group Volume Controls

A custom Home Assistant integration that creates a controllable group volume entity for each Sonos speaker (or speaker pair) in your system. The controls are integrated into the speakers' _existing_ device cards, as shown here:

![Group volume control nested within a speaker's device card](assets/control_placement.png)

___

 ***NOTE:** This integration is a **companion** to Home Assistant's native Sonos integration and does **not** replace or modify that integration. It merely exposes "Group Volume" (the average volume across a group) as a controllable entity, as Sonos does in their own apps. This custom integration can be safely added or removed at any time without detriment to the native Sonos integration.*

___

## Control Behavior

Group volume controls are exposed on every speaker (coordinator, member, or ungrouped), **not just active coordinators**, thus ensuring that all control entities remain continuously active even as system topology changes. In this way, dashboards and automations are able to target a fixed set of entities rather than tracking coordinators and availability.

* **Grouped Speakers:** The entity displays and controls the average volume across all speakers currently in that group.
* **Ungrouped Speakers:** The entity mirrors that speaker's individual volume 1:1.
* **Coordinator Visibility:** Each entity exposes `group_coordinator` and `group_coordinator_name` attributes, identifying which speaker is currently coordinating the group (or itself, when ungrouped). Useful for dashboard and automation templating.
* **Proportional Scaling:** Adjusting the slider on a grouped speaker proportionally scales every member's volume up or down, preserving their relative balance.
* **Live Updates:** Entities update in real-time as speakers join/leave groups or as volume levels change (via the Sonos app, physical controls, or HA automations).
* **Display Convention:** Group volume is truncated rather than rounded to match Sonos's native display convention (e.g., 16.9% displays as 16).

## Requirements

* Home Assistant with the native **Sonos** integration configured.
* Python 3.14+

## Installation

1. In Home Assistant, navigate to **HACS** > **⋮ (three dots)** > **Custom repositories**.
2. Add [https://github.com/TheMegamind/ha-sonos-group-volume](https://github.com/TheMegamind/ha-sonos-group-volume), set the **Type** to **Integration**, and click **Add**.
3. Find **Sonos Group Volume Controls** in HACS and click **Download**.
4. Restart Home Assistant.
5. Go to **Settings** > **Devices & Services** > **Add Integration**, search for **Sonos Group Volume Controls**, and complete the setup.
   *Note: There are no configuration options; the integration automatically detects your existing Sonos speakers.*
6. A `number.<speaker>_group_volume` entity will appear under each speaker's device card.

## How it works

* **Real-time Membership:** Group membership is read directly from each player's `group_members` attribute at the time of evaluation (no caching).
* **Event-Driven:** The integration listens for state changes across all members of a group, updating the group volume entity immediately when any member's volume changes.
* **Volume Scaling:** Adjusting the group volume entity calculates a proportional scale factor from the current group average to the target value, then applies that factor to each member individually via `media_player.volume_set`.
* **Fallback Logic:** If all group members are at 0% (making the scale factor undefined), the integration defaults to setting every member directly to the target value.

## License

Distributed under the MIT License. See `LICENSE` for details.

##  Trademarks, Disclaimers and Credits

* **SONOS** name and logo are trademarks of **Sonos, Inc.**
* **Home Assistant®** name and logo are trademarks of **Nabu Casa, Inc.**
* This custom integration is **independently maintained**, and not affiliated with or endorsed by SONOS or Nabu Casa.
