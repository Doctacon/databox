import { useSyncExternalStore } from "react";

let busy = false;
let revision = 0;
const listeners = new Set<() => void>();

function notify() {
  for (const listener of listeners) listener();
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

function busySnapshot() {
  return busy;
}

function revisionSnapshot() {
  return revision;
}

export function useCollectionMutationBusy(): boolean {
  return useSyncExternalStore(subscribe, busySnapshot, busySnapshot);
}

/** Changes exactly once after each successful collection mutation. */
export function useCollectionRevision(): number {
  return useSyncExternalStore(subscribe, revisionSnapshot, revisionSnapshot);
}

type MutationStart<T> =
  | { started: false }
  | { started: true; result: Promise<T> };

/** Atomically claims the single browser collection-mutation slot before any await. */
export function startCollectionMutation<T>(action: () => Promise<T>): MutationStart<T> {
  if (busy) return { started: false };
  busy = true;
  notify();
  const result = Promise.resolve()
    .then(action)
    .then((value) => {
      revision += 1;
      notify();
      return value;
    })
    .finally(() => {
      busy = false;
      notify();
    });
  return { started: true, result };
}
