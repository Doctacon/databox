import * as topojson from "topojson-client";

const res = await fetch("https://cdn.jsdelivr.net/npm/us-atlas@3/counties-10m.json");
const us = await res.json();

// Extract Arizona counties (FIPS 04xxx)
const azCounties = {
  type: "FeatureCollection",
  features: topojson
    .feature(us, us.objects.counties)
    .features.filter(f => String(f.id).startsWith("04")),
};

// Extract Arizona state boundary by merging all AZ counties
const azState = topojson.merge(
  us,
  us.objects.counties.geometries.filter(g => String(g.id).startsWith("04")),
);

// Simplify: round coordinates to 4 decimal places
function roundCoords(coords) {
  if (typeof coords[0] === "number") {
    return [Math.round(coords[0] * 10000) / 10000, Math.round(coords[1] * 10000) / 10000];
  }
  return coords.map(roundCoords);
}

function roundFeature(f) {
  return { ...f, geometry: { ...f.geometry, coordinates: roundCoords(f.geometry.coordinates) } };
}

const output = {
  state: roundFeature({ type: "Feature", geometry: azState, properties: {} }),
  counties: {
    type: "FeatureCollection",
    features: azCounties.features.map(f => ({
      type: "Feature",
      properties: { id: f.id },
      geometry: roundFeature(f).geometry,
    })),
  },
};

console.log(JSON.stringify(output));
