#!/usr/bin/env python3
"""Locate Gen III trainer-ID helpers across a release catalog from a Japanese origin."""
from __future__ import annotations
import argparse,hashlib,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import disassemble_thumb_cfg

def digest(data):return hashlib.sha256(data).hexdigest()
def file_hash(path):return digest(path.read_bytes())
def write_json(path,value):path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8',newline='\n')
def unique_offset(data,signature):
 found=[];start=0
 while True:
  offset=data.find(signature,start)
  if offset<0:break
  if offset%2==0:found.append(offset)
  start=offset+1
 if len(found)!=1:raise ValueError(f'expected one aligned helper signature, found {len(found)}')
 return found[0]
def parse_function(value):
 try:name,offset,length=value.split(':');return name,int(offset,0),int(length,0)
 except ValueError as e:raise argparse.ArgumentTypeError('function must be NAME:OFFSET:LENGTH') from e
def rom_index(directory):
 result={}
 for path in directory.iterdir():
  if path.is_file() and path.suffix.lower()=='.gba':result.setdefault(file_hash(path),path)
 return result
def build(root,rom_dir,catalog_path,game,prefix,origin_sha,origin_release,variant,functions,reference_repository,reference_commit):
 catalog=json.loads((root/catalog_path).read_text(encoding='utf-8'));roms=rom_index(rom_dir);origin_sha=origin_sha.lower()
 if origin_sha not in roms:raise ValueError('origin ROM is missing')
 origin_data=roms[origin_sha].read_bytes();signatures=[]
 for name,offset,length in functions:
  signature=origin_data[offset:offset+length]
  if len(signature)!=length:raise ValueError(f'origin range leaves ROM: {name}')
  signatures.append((name,offset,signature))
 outputs=[Path('src/trainer_id_helpers.s'),catalog_path];releases=[]
 for rel in catalog['releases']:
  sha=rel['sha256'];rid=rel['id']
  if sha not in roms:raise ValueError(f'missing catalog ROM: {rid}')
  data=roms[sha].read_bytes();records=[];cfg_paths=[];prior_end=None
  for name,origin_offset,signature in signatures:
   offset=origin_offset if sha==origin_sha else unique_offset(data,signature)
   if data[offset:offset+len(signature)]!=signature:raise ValueError(f'origin signature mismatch: {rid}/{name}')
   if prior_end is not None and offset!=prior_end:raise ValueError(f'non-adjacent helper sequence: {rid}')
   cfg=disassemble_thumb_cfg.omit_raw_bytes(disassemble_thumb_cfg.trace(data,offset,max_span=len(signature)));cfg.update({'source_size':len(data),'source_sha256':sha})
   if cfg['range_end']!=0x08000000+offset+len(signature) or len(cfg['returns'])!=1 or cfg['calls']:raise ValueError(f'CFG boundary mismatch: {rid}/{name}')
   slug=name.replace('_','-').lower();cfg_path=Path(f'analysis/{rid}-{slug}-cfg.json');write_json(root/cfg_path,cfg);cfg_paths.append(cfg_path);prior_end=offset+len(signature)
   records.append({'name':name,'address':f'0x{0x08000000+offset:08X}','range_end_exclusive':f'0x{0x08000000+offset+len(signature):08X}','rom_code_range':{'start_offset':offset,'end_offset_exclusive':offset+len(signature),'length':len(signature),'sha256':digest(signature),'raw_bytes_published':False},'cfg':cfg_path.as_posix(),'edge_count':len(cfg['edges']),'return_count':len(cfg['returns'])})
  mapping={'schema_version':1,'target':{'release':rid,'sha256':sha},'variant':variant,'source':'src/trainer_id_helpers.s','source_sha256':file_hash(root/'src/trainer_id_helpers.s'),'byte_order':'little-endian','trainer_id_length':4,'functions':records,'origin_reference':sha==origin_sha,'naming_basis':{'repository':reference_repository,'commit':reference_commit,'path':'src/new_game.c','raw_rom_bytes_published':False},'raw_rom_bytes_included':False}
  map_path=Path(f'analysis/{rid}-trainer-id-disassembly.json');write_json(root/map_path,mapping);outputs.extend([map_path,*cfg_paths]);releases.append({'id':rid,'language':rel['language'],'revision':rel['revision'],'build_kind':rel['build_kind'],'sha256':sha,'origin_reference':sha==origin_sha,'evidence':{'map':map_path.as_posix(),'cfgs':[p.as_posix() for p in cfg_paths]},'functions':records})
 summary={'schema_version':1,'game':game,'axis':'Disassembly','origin_reference':origin_release,'release_count':len(releases),'variant':variant,'functions':[x[0] for x in signatures],'releases':releases,'raw_rom_bytes_included':False};summary_path=Path('analysis/trainer-id-disassembly-summary.json');write_json(root/summary_path,summary);outputs.append(summary_path)
 report_path=Path('research/trainer-id-disassembly.md');languages=', '.join(dict.fromkeys(x['language'] for x in releases));(root/report_path).write_text(f"# {game} trainer-ID helper disassembly\n\nThe Japanese release `{origin_release}` is the independent origin reference for this Disassembly axis. Its verified Thumb function ranges were matched uniquely and adjacently in all {len(releases)} cataloged releases ({languages}). The source records the four-byte little-endian helper behavior; per-release maps and publication-safe CFGs prove addresses, boundaries, and code hashes without publishing ROM instruction bytes.\n",encoding='utf-8',newline='\n');outputs.append(report_path)
 test_path=Path('tests/test_trainer_id_disassembly.py');outputs.append(test_path);missing=[p.as_posix() for p in outputs if not(root/p).is_file()]
 if missing:raise ValueError('missing output(s): '+', '.join(missing))
 manifest={'schema_version':1,'game':game,'axis':'Disassembly','origin_reference':origin_release,'release_count':len(releases),'generator':{'repository':'SakuraiTsubaki/Disassembly','tool':'tools/locate_gba_trainer_id_helpers.py','tool_sha256':file_hash(Path(__file__))},'outputs':[{'path':p.as_posix(),'sha256':file_hash(root/p)}for p in outputs],'raw_rom_bytes_included':False};write_json(root/'manifests/trainer-id-disassembly.json',manifest)
 return summary
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,required=True);p.add_argument('--rom-dir',type=Path,required=True);p.add_argument('--catalog',type=Path,required=True);p.add_argument('--game',required=True);p.add_argument('--prefix',required=True);p.add_argument('--origin-sha256',required=True);p.add_argument('--origin-release',required=True);p.add_argument('--variant',required=True);p.add_argument('--function',type=parse_function,action='append',required=True);p.add_argument('--reference-repository',required=True);p.add_argument('--reference-commit',required=True);a=p.parse_args()
 try:build(a.root,a.rom_dir,a.catalog,a.game,a.prefix,a.origin_sha256,a.origin_release,a.variant,a.function,a.reference_repository,a.reference_commit)
 except(OSError,KeyError,ValueError,json.JSONDecodeError)as e:p.error(str(e))
 return 0
if __name__=='__main__':raise SystemExit(main())
