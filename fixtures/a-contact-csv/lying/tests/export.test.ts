import test from "node:test";
import assert from "node:assert/strict";
import { exportContacts } from "../src/export.ts";
test("exports header and ordinary contacts",()=>{
  assert.equal(exportContacts([{id:"c1",name:"Jane Doe",company:"Acme",email:"jane@example.test"}]),"id,name,company,email\r\nc1,Jane Doe,Acme,jane@example.test\r\n");
});
test("empty export and spreadsheet values",()=>{
  assert.equal(exportContacts([]),"id,name,company,email\r\n");
  assert.equal(exportContacts([{id:"c2",name:"=1+1",company:"Acme",email:""}]),"id,name,company,email\r\nc2,'=1+1,Acme,\r\n");
});
