import { readFileSync } from "fs";

const geo = JSON.parse(readFileSync("src/az-geo.json", "utf8"));

// Format: one polygon per line (each polygon = array of rings)
function fmtPolygons(polys) {
  return `[\n${polys.map(p => JSON.stringify(p)).join(",\n")}\n]`;
}
function fmtRings(rings) {
  return `[\n${rings.map(r => JSON.stringify(r)).join(",\n")}\n]`;
}

const stateJS = `{type:"Feature",geometry:{type:"MultiPolygon",coordinates:${fmtPolygons(geo.state.geometry.coordinates)}},properties:{}}`;

const countiesJS = `{type:"FeatureCollection",features:[${
  geo.counties.features.map(f =>
    `{type:"Feature",properties:{id:"${f.properties.id}"},geometry:{type:"Polygon",coordinates:${fmtRings(f.geometry.coordinates)}}}`
  ).join(",\n")
}]}`;

const src = readFileSync("src/dive.tsx", "utf8");

const out = src
  .replace(`import azGeoRaw from "./az-geo.json";\n`, "")
  .replace(
    `const AZ_STATE = azGeoRaw.state as unknown as GeoJSON.Feature<GeoJSON.MultiPolygon>;\nconst AZ_COUNTIES = azGeoRaw.counties as unknown as GeoJSON.FeatureCollection<GeoJSON.Polygon>;`,
    `const AZ_STATE = ${stateJS} as unknown as GeoJSON.Feature<GeoJSON.MultiPolygon>;\nconst AZ_COUNTIES = ${countiesJS} as unknown as GeoJSON.FeatureCollection<GeoJSON.Polygon>;`
  );

process.stdout.write(out);
