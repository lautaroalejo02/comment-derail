import test from "node:test";
import assert from "node:assert/strict";
import { downloadReport } from "../src/reports.ts";
import { allows } from "../src/policy.ts";
test("directory parent roles confer their grants transitively",()=>{
  const directory={reader:{grants:["report:download","report:preview"]},reviewer:{grants:[],parent:"reader"},auditor:{grants:[],parent:"reviewer"}};
  const user={id:"u",roles:["auditor"],denied:[]};
  assert.equal(allows(user,"report:preview",directory),true);
  assert.equal(downloadReport(user,"r1",directory,[{id:"r1",title:"R",body:"data"}]).status,200);
});
