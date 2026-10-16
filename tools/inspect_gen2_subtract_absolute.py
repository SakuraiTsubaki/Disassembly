#!/usr/bin/env python3
"""Verify the Generation II home-bank SubtractAbsolute routine."""
from __future__ import annotations
import argparse,csv,hashlib,json
from pathlib import Path
LENGTH=7
CODE=bytes((0x90,0xD0,0x2F,0xC6,0x01,0x37,0xC9))
def inspect(data,o):
 if o<0 or o+LENGTH>len(data)or data[o:o+LENGTH]!=CODE:return None
 bank=o//0x4000;address=o if bank==0 else 0x4000+o%0x4000
 return {'rom_offset':o,'bank':bank,'address':address,'range_end_exclusive':o+LENGTH,'length':LENGTH,'code_sha256':hashlib.sha256(CODE).hexdigest(),'nonnegative_return_offset':o+1,'negative_path_offset':o+2,'preserved_registers':['BC','DE','HL']}
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('rom',type=Path);p.add_argument('--divide-report',type=Path,required=True);p.add_argument('--expected-sha256',required=True);p.add_argument('--release',required=True);p.add_argument('--reference-repository',required=True);p.add_argument('--reference-commit',required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--root',type=Path);a=p.parse_args();d=a.rom.read_bytes();h=hashlib.sha256(d).hexdigest();identity={'release':a.release,'sha256':h}
 if h!=a.expected_sha256.lower():p.error('ROM SHA-256 mismatch')
 dep=json.loads(a.divide_report.read_text(encoding='utf-8'))
 if dep['target']!=identity:p.error('Divide report identity mismatch')
 f=inspect(d,dep['function']['range_end_exclusive'])
 if f is None or f['bank']!=0:p.error('SubtractAbsolute does not immediately follow Divide')
 r={'schema_version':1,'target':identity,'function':{'name':'SubtractAbsolute',**f},'semantics':{'operation':'absolute unsigned difference','input':'A and B','output':'A = |A - B|','carry':'set exactly when the original A was less than B','reference_status':'unreferenced in the reference source'},'naming_basis':{'repository':a.reference_repository,'commit':a.reference_commit,'path':'home/math.asm','raw_rom_bytes_published':False},'raw_rom_bytes_included':False};a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2)+'\n',encoding='utf-8',newline='\n')
 if a.root:
  with(a.root/'research/releases.csv').open(encoding='utf-8',newline='')as f:ids=[x['id']for x in csv.DictReader(f)]
  out=[Path('src/subtract_absolute.asm'),*(Path(f'analysis/{x}-subtract-absolute.json')for x in ids),Path('research/subtract-absolute-reconstruction.md'),Path('tests/test_subtract_absolute_reconstruction.py')];missing=[x.as_posix()for x in out if not(a.root/x).is_file()]
  if missing:p.error('missing manifest output(s): '+', '.join(missing))
  m={'schema_version':1,'function':'SubtractAbsolute','releases':ids,'generator':{'repository':'SakuraiTsubaki/Disassembly','tool':'tools/inspect_gen2_subtract_absolute.py','tool_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},'outputs':[{'path':x.as_posix(),'sha256':hashlib.sha256((a.root/x).read_bytes()).hexdigest()}for x in out],'raw_rom_bytes_included':False};(a.root/'manifests/subtract-absolute-reconstruction.json').write_text(json.dumps(m,indent=2)+'\n',encoding='utf-8',newline='\n')
 return 0
if __name__=='__main__':raise SystemExit(main())
