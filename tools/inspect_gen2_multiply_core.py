#!/usr/bin/env python3
"""Verify the Generation II banked _Multiply shift-add core."""
from __future__ import annotations
import argparse,csv,hashlib,json
from pathlib import Path
LENGTH=96
def expected(base):
 return bytes((0x3E,8,0x47,0xAF,0xE0,base,0xE0,base+6,0xE0,base+7,0xE0,base+8,0xE0,base+9,0xF0,base+4,0xCB,0x3F,0xE0,base+4,0x30,0x20,0xF0,base+9,0x4F,0xF0,base+3,0x81,0xE0,base+9,0xF0,base+8,0x4F,0xF0,base+2,0x89,0xE0,base+8,0xF0,base+7,0x4F,0xF0,base+1,0x89,0xE0,base+7,0xF0,base+6,0x4F,0xF0,base,0x89,0xE0,base+6,0x05,0x28,0x16,0xF0,base+3,0x87,0xE0,base+3,0xF0,base+2,0x17,0xE0,base+2,0xF0,base+1,0x17,0xE0,base+1,0xF0,base,0x17,0xE0,base,0x18,0xBF,0xF0,base+9,0xE0,base+3,0xF0,base+8,0xE0,base+2,0xF0,base+7,0xE0,base+1,0xF0,base+6,0xE0,base,0xC9))
def inspect(data,start,end):
 if start<0 or end-start!=LENGTH or end>len(data):return None
 code=data[start:end]
 if len(code)<6:return None
 base=code[5]
 if base>0xF6 or code!=expected(base):return None
 bank=start//0x4000;address=0x4000+start%0x4000 if bank else start
 h=lambda x:0xFF00+x
 return {'rom_offset':start,'bank':bank,'address':address,'range_end_exclusive':end,'length':LENGTH,'code_sha256':hashlib.sha256(code).hexdigest(),'iterations':8,'algorithm':'shift-add','hram_layout':{'multiplicand_minus_1':h(base),'multiplicand':[h(base+1),h(base+2),h(base+3)],'multiplier':h(base+4),'math_buffer_1_to_4':[h(base+6),h(base+7),h(base+8),h(base+9)],'product':[h(base),h(base+1),h(base+2),h(base+3)]}}
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('rom',type=Path);p.add_argument('--multiply-report',type=Path,required=True);p.add_argument('--divide-report',type=Path,required=True);p.add_argument('--expected-sha256',required=True);p.add_argument('--release',required=True);p.add_argument('--reference-repository',required=True);p.add_argument('--reference-commit',required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--root',type=Path);a=p.parse_args();d=a.rom.read_bytes();hsh=hashlib.sha256(d).hexdigest();identity={'release':a.release,'sha256':hsh}
 if hsh!=a.expected_sha256.lower():p.error('ROM SHA-256 mismatch')
 mul=json.loads(a.multiply_report.read_text(encoding='utf-8'));div=json.loads(a.divide_report.read_text(encoding='utf-8'))
 if mul['target']!=identity or div['target']!=identity:p.error('wrapper report identity mismatch')
 start=mul['function']['far_call']['target']['rom_offset'];end=div['function']['home_call']['target']['rom_offset'];f=inspect(d,start,end)
 if f is None or f['bank']!=1:p.error('_Multiply core does not match the wrapper target interval')
 r={'schema_version':1,'target':identity,'function':{'name':'_Multiply',**f},'semantics':{'operation':'three-byte multiplicand times one-byte multiplier using eight shift-add iterations','input':'hMultiplicand and hMultiplier','output':'four-byte hProduct','endianness':'big-endian'},'boundary_evidence':{'start':'Multiply far-call target','end':'Divide homecall target'},'naming_basis':{'repository':a.reference_repository,'commit':a.reference_commit,'path':'engine/math/math.asm','raw_rom_bytes_published':False},'raw_rom_bytes_included':False};a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2)+'\n',encoding='utf-8',newline='\n')
 if a.root:
  with(a.root/'research/releases.csv').open(encoding='utf-8',newline='')as f:ids=[x['id']for x in csv.DictReader(f)]
  out=[Path('src/multiply_core.asm'),*(Path(f'analysis/{x}-multiply-core.json')for x in ids),Path('research/multiply-core-reconstruction.md'),Path('tests/test_multiply_core_reconstruction.py')];missing=[x.as_posix()for x in out if not(a.root/x).is_file()]
  if missing:p.error('missing manifest output(s): '+', '.join(missing))
  m={'schema_version':1,'function':'_Multiply','releases':ids,'generator':{'repository':'SakuraiTsubaki/Disassembly','tool':'tools/inspect_gen2_multiply_core.py','tool_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},'outputs':[{'path':x.as_posix(),'sha256':hashlib.sha256((a.root/x).read_bytes()).hexdigest()}for x in out],'raw_rom_bytes_included':False};(a.root/'manifests/multiply-core-reconstruction.json').write_text(json.dumps(m,indent=2)+'\n',encoding='utf-8',newline='\n')
 return 0
if __name__=='__main__':raise SystemExit(main())
