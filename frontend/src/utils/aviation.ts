// Real IATA/ICAO reference data for dropdowns — no free text for airports,
// airlines, or aircraft types (validation rejects invalid codes).

export const AIRCRAFT_TYPES: Record<string, { capacity: number; body: string }> = {
  A320: { capacity: 180, body: "narrow" },
  A321: { capacity: 220, body: "narrow" },
  "B737-800": { capacity: 189, body: "narrow" },
  "B737-900": { capacity: 215, body: "narrow" },
  "B757-200": { capacity: 200, body: "narrow" },
  "B767-300": { capacity: 269, body: "wide" },
  "B777-200": { capacity: 314, body: "wide" },
  "B777-300": { capacity: 396, body: "wide" },
  "B787-8": { capacity: 248, body: "wide" },
  "B787-9": { capacity: 296, body: "wide" },
  "A330-200": { capacity: 253, body: "wide" },
  "A330-300": { capacity: 300, body: "wide" },
  "A350-900": { capacity: 325, body: "wide" },
  E175: { capacity: 76, body: "narrow" },
  "CRJ-900": { capacity: 76, body: "narrow" },
};

export const CARRIERS: Record<string, string> = {
  DL: "Delta Air Lines",
  AA: "American Airlines",
  UA: "United Airlines",
  WN: "Southwest Airlines",
  B6: "JetBlue Airways",
  AS: "Alaska Airlines",
  NK: "Spirit Airlines",
  F9: "Frontier Airlines",
  HA: "Hawaiian Airlines",
  G4: "Allegiant Air",
};

export const AIRPORTS = [
  "ATL", "JFK", "LAX", "ORD", "DFW", "DEN", "SFO", "SEA", "LAS", "MCO",
  "EWR", "CLT", "PHX", "IAH", "MIA", "BOS", "MSP", "FLL", "DTW", "PHL",
  "LGA", "BWI", "SLC", "SAN", "IAD", "DCA", "MDW", "TPA", "PDX", "STL",
];

export const SIMULATED_AIRPORTS = ["ATL", "JFK"]; // have full layout configs

export const CONGESTION_LEVELS = ["low", "moderate", "high", "severe"] as const;

export const DELAY_CAUSES = [
  "weather",
  "mechanical",
  "atc_ground_stop",
  "late_aircraft",
  "crew",
] as const;
