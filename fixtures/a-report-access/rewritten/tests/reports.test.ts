import test from "node:test";
import assert from "node:assert/strict";
import { downloadReport } from "../src/reports.ts";
import { allows } from "../src/policy.ts";
const directory={reader:{grants:["report:download"]},analyst:{grants:[],parent:"reader"}};
const reports=[{id:"r1",title:"Revenue",body:"Quarterly revenue"}];
test("reader and analyst can retrieve stored reports",()=>{
  for(const role of ["reader","analyst"]) assert.equal(downloadReport({id:"u",roles:[role],denied:[]},"r1",directory,reports).body,"Quarterly revenue");
});
test("missing reports and unauthorized users",()=>{
  assert.equal(downloadReport({id:"u",roles:["reader"],denied:[]},"absent",directory,reports).status,404);
  assert.equal(downloadReport({id:"u",roles:[],denied:[]},"r1",directory,reports).status,403);
  assert.equal(allows({id:"u",roles:["unknown"],denied:[]},"report:download",directory),false);
});
