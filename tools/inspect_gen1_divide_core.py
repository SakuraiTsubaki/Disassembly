#!/usr/bin/env python3
"""Verify the Generation I banked _Divide long-division core."""
from __future__ import annotations
import argparse,csv,hashlib,json
from pathlib import Path
LENGTH=136
def expected(base):
 return bytes((0xAF,0xE0,base+5,0xE0,base+6,0xE0,base+7,0xE0,base+8,0xE0,base+9,0x3E,9,0x5F,0xF0,base+5,0x4F,0xF0,base+1,0x91,0x57,0xF0,base+4,0x4F,0xF0,base,0x99,0x38,0x0C,0xE0,base,0x7A,0xE0,base+1,0xF0,base+9,0x3C,0xE0,base+9,0x18,0xE5,0x78,0xFE,1,0x28,0x45,0xF0,base+9,0xCB,0x27,0xE0,base+9,0xF0,base+8,0xCB,0x17,0xE0,base+8,0xF0,base+7,0xCB,0x17,0xE0,base+7,0xF0,base+6,0xCB,0x17,0xE0,base+6,0x1D,0x20,0x16,0x3E,8,0x5F,0xF0,base+5,0xE0,base+4,0xAF,0xE0,base+5,0xF0,base+1,0xE0,base,0xF0,base+2,0xE0,base+1,0xF0,base+3,0xE0,base+2,0x7B,0xFE,1,0x20,1,0x05,0xF0,base+4,0xCB,0x3F,0xE0,base+4,0xF0,base+5,0xCB,0x1F,0xE0,base+5,0x18,0x9B,0xF0,base+1,0xE0,base+4,0xF0,base+9,0xE0,base+3,0xF0,base+8,0xE0,base+2,0xF0,base+7,0xE0,base+1,0xF0,base+6,0xE0,base,0xC9))
def inspect(data,start):
 if start<0 or start+LENGTH>len(data):return None
 code=data[start:start+LENGTH]
 if len(code)<3:return None
 base=code[2]-5
 if base<0 or base>0xF6 or code!=expected(base):return None
 bank=start//0x4000;address=0x4000+start%0x4000 if bank else start;h=lambda x:0xFF00+x
 return {'rom_offset':start,'bank':bank,'address':address,'range_end_exclusive':start+LENGTH,'length':LENGTH,'code_sha256':hashlib.sha256(code).hexdigest(),'algorithm':'restoring long division','maximum_dividend_bytes':4,'hram_layout':{'dividend':[h(base),h(base+1),h(base+2),h(base+3)],'divisor':h(base+4),'divide_buffer':[h(base+5),h(base+6),h(base+7),h(base+8),h(base+9)],'remainder':h(base+4),'quotient':[h(base),h(base+1),h(base+2),h(base+3)]}}
def release_ids(root):
 p=root/'research/releases.csv'
 if p.is_file():
  with p.open(encoding='utf-8',newline='')as f:return [x['id']for x in csv.DictReader(f)]
 return [x['id']for x in json.loads((root/'analysis/aka-release-header-report.json').read_text(encoding='utf-8'))['releases']]
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('rom',type=Path);p.add_argument('--divide-report',type=Path,required=True);p.add_argument('--expected-sha256',required=True);p.add_argument('--release',required=True);p.add_argument('--reference-commit',required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--root',type=Path);a=p.parse_args();d=a.rom.read_bytes();hsh=hashlib.sha256(d).hexdigest();identity={'release':a.release,'sha256':hsh}
 if hsh!=a.expected_sha256.lower():p.error('ROM SHA-256 mismatch')
 div=json.loads(a.divide_report.read_text(encoding='utf-8'))
 if div['target']!=identity:p.error('Divide report identity mismatch')
 start=div['function']['home_call']['target']['rom_offset'];f=inspect(d,start)
 if f is None:p.error('_Divide core does not match the homecall target')
 r={'schema_version':1,'target':identity,'function':{'name':'_Divide',**f},'semantics':{'operation':'restoring long division of up to four big-endian dividend bytes','input':'hDividend, byte length in B, and hDivisor','output':'four-byte hQuotient and hRemainder','endianness':'big-endian'},'boundary_evidence':{'start':'Divide homecall target','end':'verified terminal RET after quotient stores'},'naming_basis':{'repository':'pret/pokered','commit':a.reference_commit,'path':'engine/math/multiply_divide.asm','raw_rom_bytes_published':False},'raw_rom_bytes_included':False};a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2)+'\n',encoding='utf-8',newline='\n')
 if a.root:
  ids=release_ids(a.root);out=[Path('src/divide_core.asm'),*(Path(f'analysis/{x}-divide-core.json')for x in ids),Path('research/divide-core-reconstruction.md'),Path('tests/test_divide_core_reconstruction.py')];missing=[x.as_posix()for x in out if not(a.root/x).is_file()]
  if missing:p.error('missing manifest output(s): '+', '.join(missing))
  m={'schema_version':1,'function':'_Divide','releases':ids,'generator':{'repository':'SakuraiTsubaki/Disassembly','tool':'tools/inspect_gen1_divide_core.py','tool_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},'outputs':[{'path':x.as_posix(),'sha256':hashlib.sha256((a.root/x).read_bytes()).hexdigest()}for x in out],'raw_rom_bytes_included':False};(a.root/'manifests/divide-core-reconstruction.json').write_text(json.dumps(m,indent=2)+'\n',encoding='utf-8',newline='\n')
 return 0
if __name__=='__main__':raise SystemExit(main())
