// config registry contract test: configVersion, namespace, safe slug.
import { strict as assert } from "node:assert";
import { configVersion, entries, normalizeNodeId } from "../config.mjs";

const SAFE_SLUG_RE = /^[a-z0-9][a-z0-9-]{0,62}$/;

assert.equal(configVersion, 1, "configVersion must be 1");
assert.ok(entries.length > 0, "entries must not be empty");
for (const e of entries) {
  assert.ok(SAFE_SLUG_RE.test(e.project), `project safe slug: ${e.project}`);
  assert.ok(SAFE_SLUG_RE.test(e.name), `name safe slug: ${e.name}`);
  assert.match(e.ownerRepo, /^[\w.-]+\/[\w.-]+$/, `ownerRepo owner/name: ${e.ownerRepo}`);
  assert.ok(e.figmaFileKey && e.figmaNodeId && e.url, `required fields: ${e.name}`);
}
assert.equal(normalizeNodeId("3513-155842"), "3513:155842");
assert.equal(normalizeNodeId("3513:155842"), "3513:155842");

console.log(`\n✅ visual-diff config contract: ${entries.length} entries, configVersion=${configVersion}`);
