import {test} from "node:test";
import {strict as assert} from "node:assert";
import fs from "node:fs";
const code=fs.readFileSync(new URL("../src/watchdog.js",import.meta.url),"utf8");
test("health endpoint exists and is GET only",()=>{
 assert.match(code,/request\.method !== "GET"/);
 assert.match(code,/url\.pathname !== "\/health"/);
});
test("health response explicitly says queue is not protected",()=>{
 assert.ok(code.includes('automaticQueueProtection:env.WATCHDOG_AUTO_ARM'));
 assert.match(code,/terminationArmed:armed/);
});
test("health response does not serialize Pod ID or secret",()=>{
 const body=code.slice(code.indexOf("  async fetch(request,env)"));
 assert.doesNotMatch(body,/JSON\.stringify\(env\)|JSON\.stringify\(d\)|podId:d\.podId/);
});
