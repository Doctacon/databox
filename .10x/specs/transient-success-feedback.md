Status: active
Created: 2026-07-11
Updated: 2026-07-11

# Transient success feedback

## Behavior

Every user-visible Rufous success message MUST:

- appear immediately after the confirmed successful action;
- retain existing `role="status"`/polite announcement and focused-result behavior where applicable;
- disappear 3,000 milliseconds after it is set;
- restart the full timer when another success replaces it;
- clear its timer on unmount;
- clear immediately when the owning flow starts another action or explicitly resets state.

Errors, warnings, delivery-unknown states, pending/busy states, and persisted domain status MUST NOT auto-dismiss. Removing a banner does not invalidate cached data or undo mutation.

Use one shared tested hook/helper rather than independent timers. Fake-timer tests cover create/edit/delete observations, Watches, profile controls, alerts/calendar reconciliation, planner/target success surfaces, repeated success, errors, and unmount.

## Acceptance scenarios

- New observation success is visible before 3 seconds and absent at 3 seconds.
- A second success at 2 seconds remains until 5 seconds.
- Error remains after arbitrary timer advancement.
- Unmount leaves no state update or timer leak.
