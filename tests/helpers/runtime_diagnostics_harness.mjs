import vm from 'node:vm';
import { runtimeDiagnostic } from '../../web_ui/js/runtime_diagnostics.mjs';
export function attachRuntimeDiagnostics(context, source) {
  const records=[];
  context.activeProfileRagEnabled ||= ()=>false;
  context.emitRuntimeDiagnostic = (event, scope, data) => records.push(runtimeDiagnostic(event,scope,data));
  vm.runInContext('const runtimeDiagnosticSeen = new Set();', context);
  for(const name of ['runtimeDiagnosticContext','logRuntimeDiagnostic']) {
    const start=source.indexOf(`function ${name}(`);
    vm.runInContext(source.slice(start,source.indexOf('\n}\n',start)+2),context);
  }
  return records;
}
