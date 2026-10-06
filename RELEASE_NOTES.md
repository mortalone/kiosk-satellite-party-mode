Party Mode 0.1.10

- Adds a Guest access HA switch for Music Assistant's actual guest access on the explicitly matching Party player group.
- Publishes guest access only after reading a confirmed boolean from MA. Handles MA's omitted false default. Reads back configuration after saves and does not guess off when status is unavailable, ambiguous or belongs to another group.
- Refreshes guest access every 15 seconds, independently of QR visibility and full-screen Party Mode.
- Adds a separate saved Guest QR switch. Hiding QR does not revoke MA access.
- Preserves the existing Party Mode switch and enable/disable actions.
- Switches use Kiosk's separate entity budget, without adding ordinary settings or commands.
- Adds guest-state parsing and target-isolation regression checks.
