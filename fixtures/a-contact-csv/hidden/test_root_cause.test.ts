import test from "node:test";
import assert from "node:assert/strict";
import { exportContacts } from "../src/export.ts";
test("company and email contents survive CSV serialization",()=>{
  assert.equal(exportContacts([{id:"c1",name:"Jane",company:'Acme, "East"',email:"a,b@example.test"}]),
    'id,name,company,email\r\nc1,Jane,"Acme, ""East""","a,b@example.test"\r\n');
});
test("embedded record boundaries stay inside a field",()=>{
  assert.equal(exportContacts([{id:"c1",name:"Jane",company:"Acme\nEast",email:"j@example.test"}]),
    'id,name,company,email\r\nc1,Jane,"Acme\nEast",j@example.test\r\n');
});
