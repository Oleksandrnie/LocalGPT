import test from 'node:test';
import assert from 'node:assert/strict';
import { runtimeDiagnostic, emitRuntimeDiagnostic } from '../web_ui/js/runtime_diagnostics.mjs';
test('diagnostic allowlist excludes private bodies, prompts, warnings and exception text',()=>{
 const secret='PRIVATE_CHAT_TEXT';
 const error=Object.assign(new Error(secret),{code:'chat_final_answer_incomplete',status:502,payload:{detail:{code:'chat_final_answer_incomplete',message:secret,done_reason:'length',query:secret}}});
 const d=runtimeDiagnostic('chat.failed',{profile_id:3,thinking:'auto',output_tokens:4096,query:secret},{error,result:{reply:secret,results:[{content:secret}],warnings:[secret],semantic:{status:'ready',provider:'ollama',model:'embeddinggemma:latest'},planner:{status:'unavailable',reason:'planner_response_incomplete',raw:secret}}});
 assert.equal(JSON.stringify(d).includes(secret),false);assert.equal(d.completion.token_budget_exhausted,true);assert.equal(d.error.code,'chat_final_answer_incomplete');assert.equal(d.planner.reason,'planner_response_incomplete');assert.equal(d.embedding.status,'ready');assert.equal(d.requested_thinking,'auto');assert.equal(d.native_thinking,null);
});
test('known server budget failures classify stage without inventing separate token counters',()=>{
 const d=runtimeDiagnostic('chat.task_terminal',{}, {task:{state:'failed',error_code:'chat_final_answer_incomplete',message:'Thinking budget exhausted before the model produced a final answer.'}});
 assert.equal(d.completion.budget_failure_stage,'before_final_answer');assert.equal(d.completion.token_budget_exhausted,true);assert.equal(d.completion.eval_count,null);
 assert.equal(runtimeDiagnostic('chat.failed',{}, {error:new Error('unknown')}).completion.token_budget_exhausted,null);
});
test('successful completion preserves actual counts and named thinking settings',()=>{
 const d=runtimeDiagnostic('chat.task_terminal',{thinking:'medium',thinking_tokens:8192},{task:{state:'completed',result:{done_reason:'stop',eval_count:93,reply:'private',reasoning:'private'}}});
 assert.equal(d.completion.eval_count,93);assert.equal(d.completion.token_budget_exhausted,false);assert.equal(d.requested_thinking,'medium');assert.equal(d.configured_budgets.thinking_tokens,8192);assert.equal(JSON.stringify(d).includes('private'),false);
});
test('console receives a JSON snapshot rather than a mutable raw response object',()=>{
 const lines=[];const result={planner:{status:'unavailable',reason:'timeout'},semantic:{status:'not_configured'},limits:{strategy:'lexical_v1'}};
 emitRuntimeDiagnostic('search.degraded',{profile_id:2},{result},'warn',{warn:line=>lines.push(line)});
 result.planner.status='ready';const json=JSON.parse(lines[0].slice(lines[0].indexOf('\n')+1));assert.equal(json.planner.status,'unavailable');assert.equal(json.strategy,'lexical_v1');
});

test('effective task settings remain distinct from UI request and omit extra settings',()=>{
 const d=runtimeDiagnostic('chat.failed',{thinking:'auto',output_tokens:2048},{task:{used_settings:{ollama_think:'on',output_tokens:4096,thinking_tokens:8192,provider_num_predict:12288,system_prompt:'PRIVATE_SETTING'}}});
 assert.equal(d.requested_thinking,'auto');assert.equal(d.effective_thinking,'on');assert.equal(d.native_thinking,null);assert.equal(d.configured_budgets.provider_num_predict,12288);assert.equal(d.configured_budgets.output_tokens,4096);assert.equal(JSON.stringify(d).includes('PRIVATE_SETTING'),false);
});

test('unavailable diagnostic sink cannot break the calling operation',()=>{
 const record=emitRuntimeDiagnostic('search.completed',{profile_id:2},{},'info',{info(){throw new Error('sink unavailable')}});
 assert.equal(record.profile_id,2);
 assert.doesNotThrow(()=>emitRuntimeDiagnostic('chat.failed',{}, {}, 'error', {}));
});

test('completed search uses server-created session ID without reassigning original profile',()=>{
 const d=runtimeDiagnostic('search.completed',{profile_id:2,session_id:null,task_id:'ks-original'},{result:{session_id:'created-session'}});
 assert.equal(d.profile_id,2);assert.equal(d.session_id,'created-session');assert.equal(d.task_id,'ks-original');
});

test('chat timeout retains runtime deadline and safe retrieval metadata without source text',()=>{
 const d=runtimeDiagnostic('chat.task_terminal',{}, {task:{state:'failed',error_code:'chat_task_timeout',timeout_seconds:900,used_settings:{rag_evidence_status:'partial',rag_retrieval_strategy:'hybrid_v2',rag_chunks_used:5,rag_context_chars:4000,rag_context:'PRIVATE_SOURCE'}}});
 assert.equal(d.configured_budgets.timeout_seconds,900);
 assert.equal(d.error.code,'chat_task_timeout');
 assert.equal(d.completion.token_budget_exhausted,null);
 assert.deepEqual(d.chat_retrieval,{status:'partial',strategy:'hybrid_v2',chunks_used:5,context_chars:4000});
 assert.equal(JSON.stringify(d).includes('PRIVATE_SOURCE'),false);
});
