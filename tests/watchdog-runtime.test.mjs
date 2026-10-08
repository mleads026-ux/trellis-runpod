import { strict as assert } from "node:assert";
import { test } from "node:test";
import worker, { watchdog, validateConfig } from "../src/watchdog.js";

test("HTTP health endpoint is read-only, disarmed, and does not expose secrets", async () => {
  const response = await worker.fetch(new Request("https://example.com/health"), {});
  assert.equal(response.status, 200);
  assert.equal(response.headers.get("Cache-Control"), "no-store");
  assert.deepEqual(await response.json(), {service:"trellis-runpod-watchdog",discovery:"disabled",runpodConnection:"not_tested",terminationArmed:false,automaticQueueProtection:false});
  const other = await worker.fetch(new Request("https://example.com/"), {});
  assert.equal(other.status, 404);
});

test("cron handler with no secrets remains disarmed and does not call RunPod", async () => {
  const oldFetch = globalThis.fetch;
  let networkCalls = 0;
  globalThis.fetch = async () => {networkCalls++; throw new Error("unexpected network request");};
  const pending = [];
  const oldLog = console.log;
  const oldError = console.error;
  const messages = [];
  console.log = (...args) => messages.push(args.join(" "));
  console.error = (...args) => messages.push(args.join(" "));
  try {
    await worker.scheduled({}, {}, {waitUntil(promise){pending.push(promise);}});
    assert.equal(pending.length,1);
    await Promise.all(pending);
    assert.equal(networkCalls,0);
    assert.ok(messages.some(x => x.includes("legacy_termination_disabled")));
  } finally {
    globalThis.fetch = oldFetch;
    console.log = oldLog;
    console.error = oldError;
  }
});

test("malformed UTC deadlines are rejected without network access", async () => {
  const env = {
    WATCHDOG_ARMED:"yes",
    RUNPOD_API_KEY:"mock",
    WATCHDOG_POD_ID:"test-pod",
    WATCHDOG_DEADLINE_UTC:"2026-10-08T17:00:00+03:00"
  };
  let called = false;
  await assert.rejects(watchdog(env, Date.now(), async () => {called = true;}), /Invalid UTC deadline/);
  assert.equal(called,false);
});

test("termination targets the exact configured Pod ID", async () => {
  const env = {
    WATCHDOG_ARMED:"yes",
    RUNPOD_API_KEY:"mock",
    WATCHDOG_POD_ID:"only-this-pod",
    WATCHDOG_DEADLINE_UTC:"2026-10-08T00:00:00Z"
  };
  let present = true;
  let terminatedId = null;
  const api = async (_env,query,variables) => {
    if(query.includes("podTerminate")) {
      terminatedId = variables.id;
      present = false;
      return {};
    }
    return {myself:{pods:present?[{id:"only-this-pod"},{id:"unrelated-pod"}]:[{id:"unrelated-pod"}]}};
  };
  assert.equal((await watchdog(env,Date.parse("2026-10-08T00:01:00Z"),api)).status,"terminated_verified");
  assert.equal(terminatedId,"only-this-pod");
});
