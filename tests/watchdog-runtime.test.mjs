import { strict as assert } from "node:assert";
import { test } from "node:test";
import worker, { watchdog, validateConfig } from "../src/watchdog.js";

test("HTTP status endpoint reports watchdog only, without exposing secrets", async () => {
  const response = await worker.fetch();
  assert.equal(response.status, 200);
  assert.equal(response.headers.get("Cache-Control"), "no-store");
  assert.deepEqual(await response.json(), {status:"watchdog",armedByDefault:false});
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
    assert.ok(messages.some(x => x.includes("disarmed")));
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
