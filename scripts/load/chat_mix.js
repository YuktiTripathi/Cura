// k6 load test for Cura chat (production readiness plan, 5.7).
//
//   k6 run -e BASE_URL=https://staging.cura.example -e TOKEN=<member bearer token> scripts/load/chat_mix.js
//
// Run first against staging with the model stubbed at realistic latency, then live.
// Set PEAK_VUS from real peak concurrency (open question 1 in the plan).
import http from "k6/http";
import { check, sleep } from "k6";
import { Trend, Rate } from "k6/metrics";

const BASE_URL = __ENV.BASE_URL || "http://127.0.0.1:8000";
const TOKEN = __ENV.TOKEN || "";
const PEAK = Number(__ENV.PEAK_VUS || 50);

const MIX = [
  // Deterministic lookups (~30%)
  { weight: 30, tier: "deterministic", messages: ["What is my latest HbA1c?", "Show my vitamin D result", "What was my LDL?"] },
  // Standard medical (~45%)
  { weight: 45, tier: "standard", messages: ["Why is my vitamin D low and what can I do?", "Explain my thyroid results", "What does a high LDL mean?"] },
  // Deep medical (~15%)
  { weight: 15, tier: "deep", messages: ["Give me an overall summary of my health", "How have my results changed over the last year?"] },
  // Safety (~10%), must stay fast because no model is called
  { weight: 10, tier: "safety", messages: ["I have chest pain and my left arm is numb", "Can I stop my thyroid medicine"] },
];

export const options = {
  scenarios: {
    ramp: {
      executor: "ramping-vus",
      stages: [
        { duration: "2m", target: Math.ceil(PEAK / 2) },
        { duration: "5m", target: PEAK },
        { duration: "2m", target: 0 },
      ],
    },
  },
  thresholds: {
    // Proposed targets from the plan; confirm with real peak numbers.
    "http_req_failed{expected_response:true}": ["rate<0.01"],
    "chat_seconds{tier:standard}": ["p(95)<8"],
    "chat_seconds{tier:deep}": ["p(95)<20"],
    "chat_seconds{tier:safety}": ["p(95)<1"],
    shed_rate: ["rate<0.05"],
  },
};

const chatSeconds = new Trend("chat_seconds", true);
const shedRate = new Rate("shed_rate");

function pick() {
  let roll = Math.random() * 100;
  for (const bucket of MIX) {
    if ((roll -= bucket.weight) <= 0) return bucket;
  }
  return MIX[0];
}

export default function () {
  const bucket = pick();
  const message = bucket.messages[Math.floor(Math.random() * bucket.messages.length)];
  const headers = { "Content-Type": "application/json", "Idempotency-Key": `${__VU}-${__ITER}` };
  if (TOKEN) headers.Authorization = `Bearer ${TOKEN}`;
  const res = http.post(`${BASE_URL}/api/v1/chat`, JSON.stringify({ message }), {
    headers,
    timeout: "60s",
    tags: { tier: bucket.tier },
  });
  shedRate.add(res.status === 429);
  check(res, { "status 200 or 429": (r) => r.status === 200 || r.status === 429 });
  if (res.status === 200) chatSeconds.add(res.timings.duration / 1000, { tier: bucket.tier });
  if (res.status === 429) sleep(Number(res.headers["Retry-After"] || 2));
  sleep(1 + Math.random() * 3);
}
