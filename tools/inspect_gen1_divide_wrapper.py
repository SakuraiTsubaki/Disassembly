#!/usr/bin/env python3
"""Verify Generation I Divide homecall wrapper variants."""
from __future__ import annotations
import argparse,csv,hashlib,json
from pathlib import Path
def target_offset(bank,address):return bank*0x4000+address-0x4000
def is_divide_core(data,o):return o>=0 and o+14<=len(data) and data[o]==0xAF and data[o+1]==0xE0 and data[o+3]==0xE0 and data[o+5]==0xE0 and data[o+7]==0xE0 and data[o+9]==0xE0 and data[o+11:o+14]==bytes((0x3E,9,0x5F))
def inspect(data,o):
 if o<0 or o+22>len(data)or data[o:o+3]!=bytes((0xE5,0xD5,0xC5)):return None
 variant=None
 if o+27<=len(data)and data[o+3]==0xFA and data[o+5]==0xFF and data[o+6:o+8]==bytes((0xF5,0x3E))and data[o+9]==0xE0 and data[o+11:o+14]==bytes((0xEA,0,0x20))and data[o+14]==0xCD and data[o+17]==0xF1 and data[o+18]==0xE0 and data[o+20:o+23]==bytes((0xEA,0,0x20))and data[o+23:o+27]==bytes((0xC1,0xD1,0xE1,0xC9))and data[o+4]==data[o+10]==data[o+19]:
  length=27;bank=data[o+8];address=int.from_bytes(data[o+15:o+17],'little');h=0xFF00+data[o+4];switch={'strategy':'inline','loaded_rom_bank_address':h,'rom_bank_register':0x2000,'load_form':'absolute'};variant='inline-absolute-hram'
 elif o+26<=len(data)and data[o+3]==0xF0 and data[o+5:o+7]==bytes((0xF5,0x3E))and data[o+8]==0xE0 and data[o+10:o+13]==bytes((0xEA,0,0x20))and data[o+13]==0xCD and data[o+16]==0xF1 and data[o+17]==0xE0 and data[o+19:o+22]==bytes((0xEA,0,0x20))and data[o+22:o+26]==bytes((0xC1,0xD1,0xE1,0xC9))and data[o+4]==data[o+9]==data[o+18]:
  length=26;bank=data[o+7];address=int.from_bytes(data[o+14:o+16],'little');h=0xFF00+data[o+4];switch={'strategy':'inline','loaded_rom_bank_address':h,'rom_bank_register':0x2000,'load_form':'ldh'};variant='inline-ldh'
 elif data[o+3]==0xF0 and data[o+5:o+7]==bytes((0xF5,0x3E))and data[o+8]==0xCD and data[o+11]==0xCD and data[o+14]==0xF1 and data[o+15]==0xCD and data[o+18:o+22]==bytes((0xC1,0xD1,0xE1,0xC9))and data[o+9:o+11]==data[o+16:o+18]:
  length=22;bank=data[o+7];address=int.from_bytes(data[o+12:o+14],'little');h=0xFF00+data[o+4];helper=int.from_bytes(data[o+9:o+11],'little');switch={'strategy':'helper-call','loaded_rom_bank_address':h,'helper':{'bank':0,'address':helper}};variant='helper-call'
 else:return None
 if bank==0 or not 0x4000<=address<0x8000:return None
 t=target_offset(bank,address)
 if not is_divide_core(data,t):return None
 c=data[o:o+length]
 return {'rom_offset':o,'bank':0,'address':o,'range_end_exclusive':o+length,'length':length,'code_sha256':hashlib.sha256(c).hexdigest(),'variant':variant,'home_call':{'target':{'bank':bank,'address':address,'rom_offset':t},'bank_switch':switch},'preserved_registers':['AF','BC','DE','HL']}
def release_ids(root):
 p=root/'research/releases.csv'
 if p.is_file():
  with p.open(encoding='utf-8',newline='')as f:return [x['id']for x in csv.DictReader(f)]
 return [x['id']for x in json.loads((root/'analysis/aka-release-header-report.json').read_text(encoding='utf-8'))['releases']]
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('rom',type=Path);p.add_argument('--multiply-report',type=Path,required=True);p.add_argument('--expected-sha256',required=True);p.add_argument('--release',required=True);p.add_argument('--reference-commit',required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--root',type=Path);a=p.parse_args();d=a.rom.read_bytes();hsh=hashlib.sha256(d).hexdigest();identity={'release':a.release,'sha256':hsh}
 if hsh!=a.expected_sha256.lower():p.error('ROM SHA-256 mismatch')
 mul=json.loads(a.multiply_report.read_text(encoding='utf-8'))
 if mul['target']!=identity:p.error('Multiply report identity mismatch')
 f=inspect(d,mul['function']['range_end_exclusive'])
 if f is None:p.error('Divide wrapper does not follow Multiply')
 r={'schema_version':1,'target':identity,'function':{'name':'Divide',**f},'semantics':{'operation':'preserve registers, switch to the _Divide bank, call it, and restore the prior ROM bank','input':'hDividend, byte length in B, and hDivisor','output':'hQuotient and hRemainder'},'naming_basis':{'repository':'pret/pokered','commit':a.reference_commit,'path':'home/math.asm','macro_path':'macros/farcall.asm','raw_rom_bytes_published':False},'raw_rom_bytes_included':False};a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2)+'\n',encoding='utf-8',newline='\n')
 if a.root:
  ids=release_ids(a.root);out=[Path('src/divide_wrapper.asm'),*(Path(f'analysis/{x}-divide-wrapper.json')for x in ids),Path('research/divide-wrapper-reconstruction.md'),Path('tests/test_divide_wrapper_reconstruction.py')];missing=[x.as_posix()for x in out if not(a.root/x).is_file()]
  if missing:p.error('missing manifest output(s): '+', '.join(missing))
  m={'schema_version':1,'function':'Divide','releases':ids,'generator':{'repository':'SakuraiTsubaki/Disassembly','tool':'tools/inspect_gen1_divide_wrapper.py','tool_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},'outputs':[{'path':x.as_posix(),'sha256':hashlib.sha256((a.root/x).read_bytes()).hexdigest()}for x in out],'raw_rom_bytes_included':False};(a.root/'manifests/divide-wrapper-reconstruction.json').write_text(json.dumps(m,indent=2)+'\n',encoding='utf-8',newline='\n')
 return 0
if __name__=='__main__':raise SystemExit(main())
