#!/usr/bin/env python3
"""Verify the Generation II eight-bit SimpleDivide routine."""
from __future__ import annotations
import argparse,csv,hashlib,json
from pathlib import Path
LENGTH=9;SHAPE=bytes((0x06,0x00,0x04,0x91,0x30,0xFC,0x05,0x81,0xC9))
def inspect(data,o):
 if o<0 or data[o:o+LENGTH]!=SHAPE:return None
 bank=o//0x4000;address=o if bank==0 else 0x4000+o%0x4000
 return {'rom_offset':o,'bank':bank,'address':address,'range_end_exclusive':o+LENGTH,'length':LENGTH,'code_sha256':hashlib.sha256(SHAPE).hexdigest(),'input':{'dividend':'A','divisor':'C'},'output':{'quotient':'B','remainder':'A'},'control_flow':{'subtract_loop':{'from_offset':4,'to_offset':2}}}
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('rom',type=Path);p.add_argument('--random-range-report',type=Path,required=True);p.add_argument('--expected-sha256',required=True);p.add_argument('--release',required=True);p.add_argument('--reference-repository',required=True);p.add_argument('--reference-commit',required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--root',type=Path);a=p.parse_args();d=a.rom.read_bytes();h=hashlib.sha256(d).hexdigest();identity={'release':a.release,'sha256':h}
 if h!=a.expected_sha256.lower():p.error('ROM SHA-256 mismatch')
 rr=json.loads(a.random_range_report.read_text(encoding='utf-8'))
 if rr['target']!=identity:p.error('RandomRange report identity mismatch')
 dep=rr['function']['dependencies']['SimpleDivide'];o=dep['address'] if dep['bank']==0 else dep['bank']*0x4000+dep['address']-0x4000;f=inspect(d,o)
 if f is None or(f['bank'],f['address'])!=(dep['bank'],dep['address']):p.error('SimpleDivide target shape mismatch')
 r={'schema_version':1,'target':identity,'function':{'name':'SimpleDivide',**f},'semantics':{'operation':'unsigned A / C by repeated subtraction','precondition':'C is nonzero','quotient_register':'B','remainder_register':'A'},'naming_basis':{'repository':a.reference_repository,'commit':a.reference_commit,'path':'home/math.asm','raw_rom_bytes_published':False},'raw_rom_bytes_included':False};a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2)+'\n',encoding='utf-8',newline='\n')
 if a.root:
  with(a.root/'research/releases.csv').open(encoding='utf-8',newline='')as f:ids=[x['id']for x in csv.DictReader(f)]
  out=[Path('src/simple_divide.asm'),*(Path(f'analysis/{x}-simple-divide.json')for x in ids),Path('research/simple-divide-reconstruction.md'),Path('tests/test_simple_divide_reconstruction.py')];missing=[x.as_posix()for x in out if not(a.root/x).is_file()]
  if missing:p.error('missing manifest output(s): '+', '.join(missing))
  m={'schema_version':1,'function':'SimpleDivide','releases':ids,'generator':{'repository':'SakuraiTsubaki/Disassembly','tool':'tools/inspect_gen2_simple_divide.py','tool_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},'outputs':[{'path':x.as_posix(),'sha256':hashlib.sha256((a.root/x).read_bytes()).hexdigest()}for x in out],'raw_rom_bytes_included':False};(a.root/'manifests/simple-divide-reconstruction.json').write_text(json.dumps(m,indent=2)+'\n',encoding='utf-8',newline='\n')
 return 0
if __name__=='__main__':raise SystemExit(main())
