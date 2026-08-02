import type { AlertDelivery } from "../types";

const MESSAGE = "Email alert delivery is not enabled in public Rufous.";

export async function listAlertDeliveries(): Promise<AlertDelivery[]> {
  return [];
}

export async function markAlertDelivered(_id: string): Promise<string> {
  throw new Error(MESSAGE);
}

export async function markAlertNotDelivered(_id: string): Promise<string> {
  throw new Error(MESSAGE);
}

export async function retryAlertDelivery(_id: string): Promise<string> {
  throw new Error(MESSAGE);
}
