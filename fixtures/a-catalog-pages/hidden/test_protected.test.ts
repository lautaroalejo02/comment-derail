import test from "node:test";
import assert from "node:assert/strict";
import { exportCatalog } from "../src/exporter.ts";
test("opaque empty bookmarks survive forwarding", () => {
  const seen: (string|null)[]=[];
  const gateway={fetch(_collection:string,cursor:string|null,_limit:number){
    seen.push(cursor);
    if(seen.length===1)return {items:[{id:"1",name:"A"},{id:"2",name:"B"}],next:""};
    assert.equal(cursor,"");
    return {items:[{id:"3",name:"C"}],next:null};
  }};
  assert.equal(exportCatalog(gateway,"invoices",{pageSize:2}).count,3);
  assert.deepEqual(seen,[null,""]);
});
