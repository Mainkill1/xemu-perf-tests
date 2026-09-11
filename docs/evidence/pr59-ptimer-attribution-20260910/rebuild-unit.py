import hashlib,json,pathlib,shlex,subprocess
source=pathlib.Path('/src'); build=source/'build'; out=pathlib.Path('/scratch')
commands=json.loads((build/'compile_commands.json').read_text())
replacements={}
for tail in ('test-xbox-nv2a-ptimer.c','hw/xbox/nv2a/ptimer.c','hw/xbox/nv2a/pramdac.c'):
 entry=next(x for x in commands if x['file'].endswith(tail) and 'test-xbox-nv2a-ptimer.exe.p' in x['output'])
 args=shlex.split(entry['command'])
 target=str(out/(pathlib.Path(tail).name+'.obj'))
 replacements[entry['output']]=target
 for flag,value in (('-o',target),('-MF',target+'.d'),('-MQ',target)):
  args[args.index(flag)+1]=value
 if tail=='test-xbox-nv2a-ptimer.c': args[args.index('-c')+1]=str(out/tail)
 subprocess.run(args,cwd=build,check=True)
link=subprocess.check_output(['ninja','-t','commands','tests/unit/test-xbox-nv2a-ptimer.exe'],cwd=build,text=True).splitlines()[-1]
args=shlex.split(link)
args=[replacements.get(x,x) for x in args]
args[args.index('-o')+1]=str(out/'test-xbox-nv2a-ptimer.exe')
subprocess.run(args,cwd=build,check=True)
receipt={'compiler':subprocess.check_output(['x86_64-w64-mingw32.static-gcc','--version'],text=True).splitlines()[0], 'source':'8da17c3e68c525475f55f3e9d1ddda0ad9c11d5b','runtime_source_changed':False,'rebuilt_translation_units':['test-xbox-nv2a-ptimer.c','hw/xbox/nv2a/ptimer.c','hw/xbox/nv2a/pramdac.c'],'sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (out/'test-xbox-nv2a-ptimer.c',out/'test-xbox-nv2a-ptimer.exe')},'runtime_source_sha256':{str(p.relative_to(source)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [source/'hw/xbox/nv2a/ptimer.c', source/'hw/xbox/nv2a/pramdac.c',source/'tests/unit/xbox-nv2a-ptimer-test-shim.h',source/'tests/unit/ptimer-test-stubs.c']}}
(out/'build-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt))
