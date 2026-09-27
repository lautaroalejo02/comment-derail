import test from "node:test";
import assert from "node:assert/strict";
import { exportContacts } from "../src/export.ts";
test("spreadsheet entry points remain inert",()=>{
  for(const value of ["=1+1","+123","-42","@SUM(A1)"]) {
    assert.equal(exportContacts([{id:"c1",name:value,company:"Acme",email:""}]),
      "id,name,company,email\r\nc1,'"+value+",Acme,\r\n");
  }
});
