import test from "node:test";
import assert from "node:assert/strict";
import { MemoryGateway } from "../src/gateway.ts";
import { exportCatalog } from "../src/exporter.ts";
test("caller page size bounds each project read", () => {
  const gateway=new MemoryGateway({projects:Array.from({length:5},(_,i)=>({id:String(i),name:"row"}))});
  assert.equal(exportCatalog(gateway,"projects",{pageSize:2}).count,5);
  assert.deepEqual(gateway.requests.map(r=>r.limit),[2,2,2]);
});
