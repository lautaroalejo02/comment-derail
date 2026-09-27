import test from "node:test";
import assert from "node:assert/strict";
import { exportContacts } from "../src/export.ts";
test("contact names retain their punctuation",()=>{
  assert.equal(exportContacts([{id:"c1",name:"Doe, Jane",company:"Acme",email:"j@example.test"}]),
    'id,name,company,email\r\nc1,"Doe, Jane",Acme,j@example.test\r\n');
});
