#!/usr/bin/env python3
"""Catalog ArcTan2 and structurally selected CpuSet BIOS stubs in Gen III ROMs."""
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import catalog_gen3_reset_stubs as common

FUNCTIONS={"ArcTan2":{"signature":bytes.fromhex("0adf7047"),"swi":0x0A,"arguments":["r0:x","r1:y"],"result":"r0"},"CpuSet":{"signature":bytes.fromhex("0bdf7047"),"swi":0x0B,"arguments":["r0:source","r1:destination","r2:mode"],"result":None}}
LZ_RELATIVE={"rs":{"ArcTan2":[-16],"CpuSet":[-4]},"emerald":{"ArcTan2":[-20],"CpuSet":[-8]},"frlg":{"ArcTan2":[-20,-16],"CpuSet":[-8,-4]}}
PATHS={"rs":"src/libs/libagbsyscall.s","emerald":"libagbsyscall/libagbsyscall.s","frlg":"src/libagbsyscall.s"}
ROM_BASE=0x08000000
def locate(data:bytes,signature:bytes)->list[int]:
 out=[];start=0
 while True:
  start=data.find(signature,start)
  if start<0:return out
  out.append(start);start+=1
def source_text()->str:
 lines=[".syntax unified",".thumb",""]
 for name,cfg in FUNCTIONS.items():lines += [f".global {name}",f".type {name}, %function",f"{name}:",f"    swi 0x{cfg['swi']:02X}","    bx lr",f".size {name}, . - {name}",""]
 return "\n".join(lines)
def build(root:Path,rom_dir:Path,game:str,family:str)->dict:
 profile={**common.PROFILES[family],"path":PATHS[family]};catalog_path=Path("research/releases.csv");releases=common.load_releases(root/catalog_path);roms=common.rom_index(rom_dir);source_path=Path("src/arctan2_cpuset_bios_stubs.s");(root/source_path).write_text(source_text(),encoding="utf-8",newline="\n");maps=[];records=[]
 for index,release in enumerate(releases):
  rid,sha256=release["id"],release["sha256"]
  if sha256 not in roms:raise ValueError(f"missing catalog ROM: {rid}")
  lz_path=Path(f"analysis/{rid}-lz77-bios-stubs-disassembly.json");lz=json.loads((root/lz_path).read_text(encoding="utf-8"));anchor=int(lz["functions"]["LZ77UnCompVram"]["rom_offset"]);data=roms[sha256].read_bytes();decoded={}
  for name,cfg in FUNCTIONS.items():
   matches=locate(data,cfg["signature"]);selected=[x for x in matches if x-anchor in LZ_RELATIVE[family][name]]
   if len(selected)!=1:raise ValueError(f"{name} SDK selection differs in {rid}: {matches}")
   offset=selected[0];code=data[offset:offset+4];decoded[name]={"rom_offset":offset,"address":f"0x{ROM_BASE+offset:08X}","range_end_exclusive":f"0x{ROM_BASE+offset+4:08X}","length":4,"code_sha256":common.digest(code),"software_interrupt":cfg["swi"],"arguments":cfg["arguments"],"result_register":cfg["result"],"return":"bx lr","signature_match_count":len(matches),"lz77_vram_relative_offset":offset-anchor,"selected_by_verified_sdk_layout":True}
  evidence={"schema_version":1,"axis":"Disassembly","profile":family,"target":{"release":rid,"sha256":sha256,"status":release.get("status","candidate")},"origin_reference":index==0,"source":source_path.as_posix(),"source_sha256":common.file_hash(root/source_path),"functions":decoded,"verified_layout":{"lz77_vram_anchor":lz["functions"]["LZ77UnCompVram"]["address"],"allowed_family_relative_offsets":LZ_RELATIVE[family]},"cross_reference":{"lz77_bios_stubs":lz_path.as_posix(),"sha256":common.file_hash(root/lz_path)},"naming_basis":profile,"raw_rom_bytes_included":False}
  map_path=Path(f"analysis/{rid}-arctan2-cpuset-stubs-disassembly.json");common.write_json(root/map_path,evidence);maps.append(map_path);records.append({"id":rid,"language":release["language"],"revision":int(release["revision"]),"status":release.get("status","candidate"),"sha256":sha256,"origin_reference":index==0,"addresses":{n:v["address"]for n,v in decoded.items()},"cpuset_signature_match_count":decoded["CpuSet"]["signature_match_count"],"evidence":map_path.as_posix()})
 summary={"schema_version":1,"axis":"Disassembly","game":game,"library":"libagbsyscall","functions":list(FUNCTIONS),"profile":family,"origin_reference":releases[0]["id"],"release_count":len(records),"source":source_path.as_posix(),"releases":records,"raw_rom_bytes_included":False};summary_path=Path("analysis/arctan2-cpuset-stubs-disassembly-summary.json");common.write_json(root/summary_path,summary)
 languages=", ".join(dict.fromkeys(x["language"]for x in records));duplicates=sum(x["cpuset_signature_match_count"]>1 for x in records);research_path=Path("research/arctan2-cpuset-stubs-disassembly.md");(root/research_path).write_text(f"# {game} ArcTan2 and CpuSet BIOS stubs\n\n{releases[0]['id']} is the Japanese origin reference. All {len(records)} releases ({languages}) verify ArcTan2 SWI 0x0A and CpuSet SWI 0x0B at SDK-layout offsets from the LZ77 VRAM wrapper. CpuSet has duplicate byte signatures in {duplicates} build(s), so the selected function is the sole candidate at the verified -4/-8 layout position. Pinned libagbsyscall sources corroborate symbols and calling conventions. No ROM bytes are published.\n",encoding="utf-8",newline="\n")
 test_path=Path("tests/test_arctan2_cpuset_stubs_disassembly.py");outputs=[catalog_path,source_path,summary_path,*maps,research_path,test_path];missing=[p.as_posix()for p in outputs if not(root/p).is_file()]
 if missing:raise ValueError("missing output(s): "+", ".join(missing))
 common.write_json(root/"manifests/arctan2-cpuset-stubs-disassembly.json",{"schema_version":1,"axis":"Disassembly","game":game,"library":"libagbsyscall","functions":list(FUNCTIONS),"profile":family,"origin_reference":releases[0]["id"],"release_count":len(records),"generator":{"repository":"SakuraiTsubaki/Disassembly","tool":"tools/catalog_gen3_arctan2_cpuset_stubs.py","tool_sha256":common.file_hash(Path(__file__))},"outputs":[{"path":p.as_posix(),"sha256":common.file_hash(root/p)}for p in outputs],"raw_rom_bytes_included":False});return summary
def main()->int:
 p=argparse.ArgumentParser(description=__doc__);p.add_argument("--root",type=Path,required=True);p.add_argument("--rom-dir",type=Path,required=True);p.add_argument("--game",required=True);p.add_argument("--family",choices=sorted(common.PROFILES),required=True);a=p.parse_args()
 try:build(a.root,a.rom_dir,a.game,a.family)
 except(OSError,KeyError,ValueError,json.JSONDecodeError)as e:p.error(str(e))
 return 0
if __name__=="__main__":raise SystemExit(main())
