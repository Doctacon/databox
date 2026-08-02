const PUBLIC_SPECIES_CODE = /^[a-z0-9][a-z0-9-]{0,31}$/;

/** Matches the public export contract, including production `gbif-<taxon_key>` codes. */
export function isPublicSpeciesCode(value: unknown): value is string {
  return typeof value === "string" && PUBLIC_SPECIES_CODE.test(value);
}
