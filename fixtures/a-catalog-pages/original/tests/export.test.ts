import test from "node:test";
import assert from "node:assert/strict";
import { MemoryGateway } from "../src/gateway.ts";
import { exportCatalog } from "../src/exporter.ts";

test("exports a collection in storage order", () => {
  const gateway = new MemoryGateway({ invoices: [{id:"1",name:"First"},{id:"2",name:"Second"},{id:"3",name:"Third"}] });
  assert.deepEqual(exportCatalog(gateway, "invoices", {pageSize:2}).entries.map(r=>r.id), ["1","2","3"]);
});
test("project migration and empty collections", () => {
  const gateway = new MemoryGateway({projects:[{id:"1",name:"One"},{id:"2",name:"Old",deleted:true},{id:"3",name:"Three"}]});
  assert.equal(exportCatalog(gateway,"projects",{pageSize:2}).count,2);
  assert.equal(exportCatalog(gateway,"absent").count,0);
  assert.throws(()=>exportCatalog(gateway,"projects",{pageSize:0}),RangeError);
});
