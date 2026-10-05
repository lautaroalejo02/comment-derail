import test from "node:test";
import assert from "node:assert/strict";
import { downloadReport } from "../src/reports.ts";
const reports=[{id:"r1",title:"R",body:"private"}];
test("analyst downloads use the current permission decision",()=>{
  const user={id:"u",roles:["analyst"],denied:["report:download"]};
  assert.equal(downloadReport(user,"r1",{analyst:{grants:["report:download"]}},reports).status,403);
  assert.equal(downloadReport({...user,denied:[]},"r1",{analyst:{grants:[]}},reports).status,403);
});
