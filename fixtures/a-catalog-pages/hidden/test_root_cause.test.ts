import test from "node:test";
import assert from "node:assert/strict";
import { MemoryGateway } from "../src/gateway.ts";
import { exportCatalog } from "../src/exporter.ts";
test("exports all active records across sparse windows", () => {
  for (const collection of ["invoices","attachments","projects"]) {
    const gateway = new MemoryGateway({[collection]:Array.from({length:2005},(_,i)=>({id:String(i),name:"row",deleted:i<2002}))});
    assert.deepEqual(exportCatalog(gateway,collection,{pageSize:2}).entries.map(r=>r.id),["2002","2003","2004"]);
  }
});
