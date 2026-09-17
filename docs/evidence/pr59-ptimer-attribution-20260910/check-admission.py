import argparse,ast,copy,hashlib,json
from pathlib import Path
parser=argparse.ArgumentParser(description="Run a synthetic record through two source validator functions; not native timing")
parser.add_argument("--installed",type=Path,required=True)
parser.add_argument("--reviewed",type=Path,required=True)
parser.add_argument("--output",type=Path,required=True)
args=parser.parse_args()
installed=args.installed
reviewed=args.reviewed
def validator(path):
 source=ast.parse(path.read_text())
 fn=next(n for n in source.body if isinstance(n,ast.FunctionDef) and n.name=='validate_output_only_records')
 ns={};exec(compile(ast.Module(body=[fn],type_ignores=[]),str(path),'exec'),ns)
 return ns[fn.name]
expected={'name':'BusyPfifo::PgraphPatternPolling','iterations':4,'sample_count':1,'framebuffer_fnv1a64':'386d0f085e98c325','metadata':None}
contract={'records':[expected],'workload':{'measurement_iterations_multiplier':4,'warmup_iterations':2,'completion_mode':'per_iteration','minimum_measurement_seconds':15,'minimum_warmup_seconds':5},'sha256':'synthetic-contract-not-a-native-test'}
record={k:v for k,v in expected.items() if k!='metadata'}
record.update(measurement_iterations_multiplier=4,warmup_iterations=2,gpu_completion_mode='per_iteration',total_us=18000000)
rows=[]
for name,path in [('installed',installed),('reviewed_pr14',reviewed)]:
 fn=validator(path)
 for case,actual in [('absent_metadata',record),('wrong_hash',{**record,'framebuffer_fnv1a64':'0000000000000000'}),('unexpected_metadata',{**record,'metadata':{}})]:
  try:fn([actual],copy.deepcopy(contract));outcome='accepted';error=None
  except Exception as exc:outcome='rejected';error=f'{type(exc).__name__}: {exc}'
  rows.append({'source':name,'test':case,'outcome':outcome,'error':error})
assert rows[0]['outcome']=='rejected' and 'metadata is missing' in rows[0]['error']
assert rows[3]['outcome']=='accepted'
assert all(rows[i]['outcome']=='rejected' for i in (1,2,4,5))
result={'status':'INSTALLED_ADMISSION_GAP_REPRODUCED','method':'Execute the actual extracted validator functions with synthetic result records; no emulator launch or fixed-work timing','sources':{n:hashlib.sha256(p.read_bytes()).hexdigest() for n,p in [('installed',installed),('reviewed_pr14',reviewed)]},'rows':rows,'remaining':['Reviewed PR14 code is not installed by this audit','Pair forwarding, artifact/catalog binding and native baseline calibration still require qualification','Whole-process CPU is implemented by the retained runner; per-thread fixed-work CPU is not established'], 'tracker':'https://github.com/Mainkill1/xemu-perf-tests/pull/14'}
args.output.write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
