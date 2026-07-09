import type { ApiError, CreatePlanInput, PlanSummary, TripPlanDetail } from "./types";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  const body = (await response.json()) as T | ApiError;
  if (!response.ok) {
    const error = body as ApiError;
    throw new Error(error.error?.message || "The local service could not complete the request");
  }
  return body as T;
}

export async function listPlans(): Promise<PlanSummary[]> {
  const body = await request<{ plans: PlanSummary[] }>("/api/trip-plans");
  return body.plans;
}

export function getPlan(id: string): Promise<TripPlanDetail> {
  return request<TripPlanDetail>(`/api/trip-plans/${encodeURIComponent(id)}`);
}

export function createPlan(input: CreatePlanInput): Promise<TripPlanDetail> {
  return request<TripPlanDetail>("/api/trip-plans", {
    method: "POST",
    body: JSON.stringify(input),
  });
}
