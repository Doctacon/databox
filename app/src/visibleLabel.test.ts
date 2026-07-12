import { describe, expect, it } from "vitest";
import appSource from "./App.tsx?raw";
import birdPagesSource from "./BirdPages.tsx?raw";
import fieldMapSource from "./FieldMap.tsx?raw";
import myBirdsSource from "./MyBirds.tsx?raw";
import targetBirdSource from "./TargetBird.tsx?raw";
import { compareVisibleLabels } from "./visibleLabel";

const selectInventory = [
  [appSource, "evidence-page-size-", "numeric page-size progression"],
  [appSource, "id=\"duration_minutes\"", "numeric duration progression"],
  [appSource, "id=\"skill_level\"", "ordinal skill progression with sentinel first"],
  [appSource, "id=\"plan-history\"", "chronological saved-plan history with sentinel first"],
  [targetBirdSource, "id=\"target-duration\"", "numeric duration progression"],
  [fieldMapSource, "id=\"map-species\"", "sentinel then alphabetical bird labels"],
  [fieldMapSource, "id=\"map-family\"", "sentinel then alphabetical family labels"],
  [fieldMapSource, "id=\"map-recency\"", "ordinal recency windows"],
  [myBirdsSource, "observation-species-", "alphabetical bird labels"],
  [myBirdsSource, "id=\"new-watch-species\"", "alphabetical available bird labels"],
  [birdPagesSource, "id=\"bird-sort\"", "semantic sort actions"],
  [birdPagesSource, "id=\"bird-category\"", "sentinel then alphabetical text"],
  [birdPagesSource, "id=\"bird-family\"", "sentinel then alphabetical text"],
  [birdPagesSource, "id=\"bird-habitat\"", "sentinel then alphabetical text"],
  [birdPagesSource, "id=\"bird-weight\"", "numeric weight progression with sentinel first"],
] as const;

describe("visible text select ordering", () => {
  it("inventories and classifies every current native select", () => {
    expect([appSource, birdPagesSource, fieldMapSource, myBirdsSource, targetBirdSource]
      .reduce((count, source) => count + (source.match(/<select\b/g)?.length ?? 0), 0)).toBe(selectInventory.length);
    for (const [source, marker, classification] of selectInventory) {
      expect(source, classification).toContain(marker);
    }
  });

  it("uses deterministic English case-insensitive numeric labels and explicit ties", () => {
    const rows = [
      { label: "Zebra", value: "z" }, { label: "alpha 10", value: "b" },
      { label: "Alpha 2", value: "c" }, { label: "same", value: "bird10" },
      { label: "Same", value: "bird2" },
    ];
    expect(rows.sort((left, right) => compareVisibleLabels(left.label, right.label, left.value, right.value)))
      .toEqual([
        { label: "Alpha 2", value: "c" }, { label: "alpha 10", value: "b" },
        { label: "Same", value: "bird2" }, { label: "same", value: "bird10" },
        { label: "Zebra", value: "z" },
      ]);
  });

  it("keeps numeric, ordinal, chronological, and semantic authored orders", () => {
    expect(appSource).toContain('<option value="30">30 minutes</option><option value="60">60 minutes</option>');
    expect(appSource).toContain('<option value="">Not specified</option><option value="beginner">Beginner</option>');
    expect(appSource).toContain("{plans.map((plan) =>");
    expect(targetBirdSource).toContain('<option value="30">30 minutes</option><option value="60">1 hour</option>');
    expect(birdPagesSource).toContain('<option value="all">All weights</option><option value="tiny">Tiny');
    expect(birdPagesSource).toContain('<option value="name-asc">Name A–Z</option><option value="name-desc">Name Z–A</option>');
  });
});
