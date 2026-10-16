#!/usr/bin/env python3
"""Verify the Generation II home-bank Divide homecall wrapper."""
from __future__ import annotations
import argparse,csv,hashlib,json
from pathlib import Path
LENGTH=18
def inspect(data,o):
 if o<0 or o+LENGTH>len(data):return None
 c=data[o:o+LENGTH]
 if c[0:4]!=bytes((0xE5,0xD5,0xC5,0xF0))or c[5:7]!=bytes((0xF5,0x3E))or c[8:10]!=bytes((0xD7,0xCD))or c[12:18]!=bytes((0xF1,0xD7,0xC1,0xD1,0xE1,0xC9)):return None
 bank=c[7];address=int.from_bytes(c[10:12],'little')
 if bank==0 or not 0x4000<=address<0x8000:return None
 target=bank*0x4000+address-0x4000
 if target>=len(data):return None
 home_bank=o//0x4000;home_address=o if home_bank==0 else 0x4000+o%0x4000
 return {'rom_offset':o,'bank':home_bank,'address':home_address,'range_end_exclusive':o+LENGTH,'length':LENGTH,'code_sha256':hashlib.sha256(c).hexdigest(),'home_call':{'saved_rom_bank_hram_address':0xFF00+c[4],'bankswitch':{'rst_opcode':'RST $10','vector':16},'target':{'bank':bank,'address':address,'rom_offset':target}},'preserved_registers':['AF','BC','DE','HL']}
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('rom',type=Path);p.add_argument('--multiply-report',type=Path,required=True);p.add_argument('--expected-sha256',required=True);p.add_argument('--release',required=True);p.add_argument('--reference-repository',required=True);p.add_argument('--reference-commit',required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--root',type=Path);a=p.parse_args();d=a.rom.read_bytes();h=hashlib.sha256(d).hexdigest();identity={'release':a.release,'sha256':h}
 if h!=a.expected_sha256.lower():p.error('ROM SHA-256 mismatch')
 dep=json.loads(a.multiply_report.read_text(encoding='utf-8'))
 if dep['target']!=identity:p.error('Multiply report identity mismatch')
 f=inspect(d,dep['function']['range_end_exclusive'])
 if f is None or f['bank']!=0:p.error('Divide wrapper does not follow Multiply')
 r={'schema_version':1,'target':identity,'function':{'name':'Divide',**f},'semantics':{'operation':'preserve registers, switch to the _Divide bank, call it, and restore the prior ROM bank','input':'hDividend (up to 4 bytes), length in B, and hDivisor','output':'hQuotient and hRemainder','register_preservation':'AF, BC, DE, and HL are restored by the wrapper'},'naming_basis':{'repository':a.reference_repository,'commit':a.reference_commit,'path':'home/math.asm','macro_path':'macros/farcall.asm','raw_rom_bytes_published':False},'raw_rom_bytes_included':False};a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2)+'\n',encoding='utf-8',newline='\n')
 if a.root:
  with(a.root/'research/releases.csv').open(encoding='utf-8',newline='')as f:ids=[x['id']for x in csv.DictReader(f)]
  out=[Path('src/divide_wrapper.asm'),*(Path(f'analysis/{x}-divide-wrapper.json')for x in ids),Path('research/divide-wrapper-reconstruction.md'),Path('tests/test_divide_wrapper_reconstruction.py')];missing=[x.as_posix()for x in out if not(a.root/x).is_file()]
  if missing:p.error('missing manifest output(s): '+', '.join(missing))
  m={'schema_version':1,'function':'Divide','releases':ids,'generator':{'repository':'SakuraiTsubaki/Disassembly','tool':'tools/inspect_gen2_divide_wrapper.py','tool_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},'outputs':[{'path':x.as_posix(),'sha256':hashlib.sha256((a.root/x).read_bytes()).hexdigest()}for x in out],'raw_rom_bytes_included':False};(a.root/'manifests/divide-wrapper-reconstruction.json').write_text(json.dumps(m,indent=2)+'\n',encoding='utf-8',newline='\n')
 return 0
if __name__=='__main__':raise SystemExit(main())
