import assert from "node:assert/strict";
import test from "node:test";
import { clearSensitiveBrowserData, scopedMatchStorageKey } from "../src/lib/sensitive-storage.ts";

function storage() {
  const values = {};
  Object.defineProperties(values, {
    getItem: { value: (key) => values[key] ?? null },
    setItem: { value: (key, value) => { values[key] = String(value); } },
    removeItem: { value: (key) => { delete values[key]; } },
  });
  return values;
}

test("A logout and B login cannot reveal A's local analysis", () => {
  globalThis.localStorage = storage();
  globalThis.sessionStorage = storage();
  globalThis.window = {};
  localStorage.setItem("kafundo_token", "A-token");
  localStorage.setItem("kafundo_user", JSON.stringify({ id: "A", default_organization_id: "org-A" }));
  const aKey = scopedMatchStorageKey();
  localStorage.setItem(aKey, JSON.stringify({ result: { matches: ["A-secret"] } }));
  localStorage.setItem("kafundo_device_pipeline", "A-pipeline");
  sessionStorage.setItem("kafundo_devices_filters:/devices", "A-filters");
  localStorage.setItem("theme", "dark");

  clearSensitiveBrowserData();
  assert.equal(localStorage.getItem(aKey), null);
  assert.equal(localStorage.getItem("kafundo_device_pipeline"), null);
  assert.equal(sessionStorage.getItem("kafundo_devices_filters:/devices"), null);
  assert.equal(localStorage.getItem("theme"), "dark");

  localStorage.setItem("kafundo_user", JSON.stringify({ id: "B", default_organization_id: "org-B" }));
  assert.notEqual(scopedMatchStorageKey(), aKey);
  assert.equal(localStorage.getItem(scopedMatchStorageKey()), null);
  delete globalThis.window;
  delete globalThis.localStorage;
  delete globalThis.sessionStorage;
});
