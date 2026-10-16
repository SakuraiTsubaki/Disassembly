#!/usr/bin/env python3
"""Verify the Generation II home-bank SimpleMultiply routine."""
from __future__ import annotations
import argparse,csv,hashlib,json
from pathlib import Path
LENGTH=11
CODE=bytes((0xA7,0xC8,0xC5,0x47,0xAF,0x81,0x05,0x20,0xFC,0xC1,0xC9))
def inspect(data,o):
 if o<0 or o+LENGTH>len(data)or data[o:o+LENGTH]!=CODE:return None
 bank=o//0x4000;address=o if bank==0 else 0x4000+o%0x4000
 return {'rom_offset':o,'bank':bank,'address':address,'range_end_exclusive':o+LENGTH,'length':LENGTH,'code_sha256':hashlib.sha256(CODE).hexdigest(),'loop':{'body_offset':o+5,'conditional_branch_offset':o+7,'target_offset':o+5},'zero_shortcut':True,'preserved_registers':['BC']}
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('rom',type=Path);p.add_argument('--simple-divide-report',type=Path,required=True);p.add_argument('--expected-sha256',required=True);p.add_argument('--release',required=True);p.add_argument('--reference-repository',required=True);p.add_argument('--reference-commit',required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--root',type=Path);a=p.parse_args();d=a.rom.read_bytes();h=hashlib.sha256(d).hexdigest();identity={'release':a.release,'sha256':h}
 if h!=a.expected_sha256.lower():p.error('ROM SHA-256 mismatch')
 dep=json.loads(a.simple_divide_report.read_text(encoding='utf-8'))
 if dep['target']!=identity:p.error('SimpleDivide report identity mismatch')
 o=dep['function']['rom_offset']-LENGTH;f=inspect(d,o)
 if f is None or f['bank']!=0 or f['range_end_exclusive']!=dep['function']['rom_offset']:p.error('SimpleMultiply does not immediately precede SimpleDivide')
 r={'schema_version':1,'target':identity,'function':{'name':'SimpleMultiply',**f},'semantics':{'operation':'unsigned repeated-add multiplication','input':'A and C','output':'A = A * C modulo 256','zero_case':'A = 0 returns immediately','register_preservation':'BC is restored'},'naming_basis':{'repository':a.reference_repository,'commit':a.reference_commit,'path':'home/math.asm','raw_rom_bytes_published':False},'raw_rom_bytes_included':False};a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2)+'\n',encoding='utf-8',newline='\n')
 if a.root:
  with(a.root/'research/releases.csv').open(encoding='utf-8',newline='')as f:ids=[x['id']for x in csv.DictReader(f)]
  out=[Path('src/simple_multiply.asm'),*(Path(f'analysis/{x}-simple-multiply.json')for x in ids),Path('research/simple-multiply-reconstruction.md'),Path('tests/test_simple_multiply_reconstruction.py')];missing=[x.as_posix()for x in out if not(a.root/x).is_file()]
  if missing:p.error('missing manifest output(s): '+', '.join(missing))
  m={'schema_version':1,'function':'SimpleMultiply','releases':ids,'generator':{'repository':'SakuraiTsubaki/Disassembly','tool':'tools/inspect_gen2_simple_multiply.py','tool_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},'outputs':[{'path':x.as_posix(),'sha256':hashlib.sha256((a.root/x).read_bytes()).hexdigest()}for x in out],'raw_rom_bytes_included':False};(a.root/'manifests/simple-multiply-reconstruction.json').write_text(json.dumps(m,indent=2)+'\n',encoding='utf-8',newline='\n')
 return 0
if __name__=='__main__':raise SystemExit(main())
