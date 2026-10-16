#!/usr/bin/env python3
"""Verify the Generation II home-bank Multiply far-call wrapper."""
from __future__ import annotations
import argparse,csv,hashlib,json
from pathlib import Path
LENGTH=11
def inspect(data,o):
 if o<0 or o+LENGTH>len(data):return None
 c=data[o:o+LENGTH]
 if c[0:3]!=bytes((0xE5,0xC5,0x21))or c[5]!=0x3E or c[7:11]!=bytes((0xCF,0xC1,0xE1,0xC9)):return None
 bank=c[6];address=int.from_bytes(c[3:5],'little')
 if bank==0 or not 0x4000<=address<0x8000:return None
 target=bank*0x4000+address-0x4000
 if target>=len(data):return None
 home_bank=o//0x4000;home_address=o if home_bank==0 else 0x4000+o%0x4000
 return {'rom_offset':o,'bank':home_bank,'address':home_address,'range_end_exclusive':o+LENGTH,'length':LENGTH,'code_sha256':hashlib.sha256(c).hexdigest(),'far_call':{'rst_opcode':'RST $08','vector':8,'target':{'bank':bank,'address':address,'rom_offset':target}},'preserved_registers':['BC','HL']}
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('rom',type=Path);p.add_argument('--simple-divide-report',type=Path,required=True);p.add_argument('--expected-sha256',required=True);p.add_argument('--release',required=True);p.add_argument('--reference-repository',required=True);p.add_argument('--reference-commit',required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--root',type=Path);a=p.parse_args();d=a.rom.read_bytes();h=hashlib.sha256(d).hexdigest();identity={'release':a.release,'sha256':h}
 if h!=a.expected_sha256.lower():p.error('ROM SHA-256 mismatch')
 dep=json.loads(a.simple_divide_report.read_text(encoding='utf-8'))
 if dep['target']!=identity:p.error('SimpleDivide report identity mismatch')
 f=inspect(d,dep['function']['range_end_exclusive'])
 if f is None or f['bank']!=0:p.error('Multiply wrapper does not follow SimpleDivide')
 r={'schema_version':1,'target':identity,'function':{'name':'Multiply',**f},'semantics':{'operation':'preserve HL/BC and far-call _Multiply','input':'hMultiplicand (3 bytes) and hMultiplier','output':'hProduct','register_preservation':'BC and HL are restored'},'naming_basis':{'repository':a.reference_repository,'commit':a.reference_commit,'path':'home/math.asm','macro_path':'macros/farcall.asm','raw_rom_bytes_published':False},'raw_rom_bytes_included':False};a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2)+'\n',encoding='utf-8',newline='\n')
 if a.root:
  with(a.root/'research/releases.csv').open(encoding='utf-8',newline='')as f:ids=[x['id']for x in csv.DictReader(f)]
  out=[Path('src/multiply_wrapper.asm'),*(Path(f'analysis/{x}-multiply-wrapper.json')for x in ids),Path('research/multiply-wrapper-reconstruction.md'),Path('tests/test_multiply_wrapper_reconstruction.py')];missing=[x.as_posix()for x in out if not(a.root/x).is_file()]
  if missing:p.error('missing manifest output(s): '+', '.join(missing))
  m={'schema_version':1,'function':'Multiply','releases':ids,'generator':{'repository':'SakuraiTsubaki/Disassembly','tool':'tools/inspect_gen2_multiply_wrapper.py','tool_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},'outputs':[{'path':x.as_posix(),'sha256':hashlib.sha256((a.root/x).read_bytes()).hexdigest()}for x in out],'raw_rom_bytes_included':False};(a.root/'manifests/multiply-wrapper-reconstruction.json').write_text(json.dumps(m,indent=2)+'\n',encoding='utf-8',newline='\n')
 return 0
if __name__=='__main__':raise SystemExit(main())
