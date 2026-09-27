import test from "node:test";
import assert from "node:assert/strict";
import { downloadReport } from "../src/reports.ts";
test("suspension overrides an administrator grant",()=>{
  const user={id:"u",roles:["administrator"],denied:["report:download"]};
  const directory={administrator:{grants:["report:download"]}};
  assert.equal(downloadReport(user,"r1",directory,[{id:"r1",title:"R",body:"secret"}]).status,403);
});
