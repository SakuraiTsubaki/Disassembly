#!/usr/bin/env python3
"""Catalog the MultiBoot BIOS wrapper in Emerald and FRLG ROMs."""
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import catalog_gen3_reset_stubs as common

SIGNATURE=bytes.fromhex("012125df7047")
FUNCTION_LENGTH=6
LZ_RELATIVE={"emerald":8,"frlg":8}
PATHS={"emerald":"libagbsyscall/libagbsyscall.s","frlg":"src/libagbsyscall.s"}

def locate(data:bytes)->list[int]:
 out=[];start=0
 while True:
  start=data.find(SIGNATURE,start)
  if start<0:return out
  out.append(start);start+=1

def source_text()->str:
 return """.syntax unified
.thumb

.global MultiBoot
.type MultiBoot, %function
MultiBoot:
    movs r1, 1
    swi 0x25
    bx lr
.size MultiBoot, . - MultiBoot
"""

def build(root:Path,rom_dir:Path,game:str,family:str)->dict:
 profile={**common.PROFILES[family],"path":PATHS[family]};catalog_path=Path("research/releases.csv");releases=common.load_releases(root/catalog_path);roms=common.rom_index(rom_dir);source_path=Path("src/multiboot_bios_stub.s");(root/source_path).write_text(source_text(),encoding="utf-8",newline="\n");maps=[];records=[]
 for index,release in enumerate(releases):
  rid,sha256=release["id"],release["sha256"]
  if sha256 not in roms:raise ValueError(f"missing catalog ROM: {rid}")
  lz_path=Path(f"analysis/{rid}-lz77-bios-stubs-disassembly.json");lz=json.loads((root/lz_path).read_text(encoding="utf-8"));anchor=int(lz["functions"]["LZ77UnCompVram"]["rom_offset"]);data=roms[sha256].read_bytes();matches=locate(data);offset=anchor+LZ_RELATIVE[family]
  if offset not in matches:raise ValueError(f"MultiBoot SDK selection differs in {rid}: {matches}")
  function={"name":"MultiBoot","rom_offset":offset,"address":f"0x{common.ROM_BASE+offset:08X}","range_end_exclusive":f"0x{common.ROM_BASE+offset+FUNCTION_LENGTH:08X}","length":FUNCTION_LENGTH,"code_sha256":common.digest(data[offset:offset+FUNCTION_LENGTH]),"mode_register":"r1","mode_value":1,"parameter_register":"r0","result_register":"r0","software_interrupt":0x25,"return":"bx lr","signature_match_count":len(matches),"lz77_vram_relative_offset":offset-anchor,"selected_by_verified_sdk_layout":True}
  evidence={"schema_version":1,"axis":"Disassembly","profile":family,"target":{"release":rid,"sha256":sha256,"status":release.get("status","candidate")},"origin_reference":index==0,"source":source_path.as_posix(),"source_sha256":common.file_hash(root/source_path),"function":function,"verified_layout":{"lz77_vram_anchor":lz["functions"]["LZ77UnCompVram"]["address"],"family_relative_offset":LZ_RELATIVE[family]},"cross_reference":{"lz77_bios_stubs":lz_path.as_posix(),"sha256":common.file_hash(root/lz_path)},"naming_basis":profile,"raw_rom_bytes_included":False}
  map_path=Path(f"analysis/{rid}-multiboot-stub-disassembly.json");common.write_json(root/map_path,evidence);maps.append(map_path);records.append({"id":rid,"language":release["language"],"revision":int(release["revision"]),"status":release.get("status","candidate"),"sha256":sha256,"origin_reference":index==0,"address":function["address"],"signature_match_count":len(matches),"evidence":map_path.as_posix()})
 summary={"schema_version":1,"axis":"Disassembly","game":game,"library":"libagbsyscall","function":"MultiBoot","profile":family,"origin_reference":releases[0]["id"],"release_count":len(records),"source":source_path.as_posix(),"releases":records,"raw_rom_bytes_included":False};summary_path=Path("analysis/multiboot-stub-disassembly-summary.json");common.write_json(root/summary_path,summary)
 languages=", ".join(dict.fromkeys(x["language"] for x in records));research_path=Path("research/multiboot-stub-disassembly.md");(root/research_path).write_text(f"# {game} MultiBoot BIOS stub\n\n{releases[0]['id']} is the Japanese origin reference. All {len(records)} cataloged releases ({languages}) verify the six-byte MultiBoot wrapper at +8 from LZ77UnCompVram. It fixes r1 to mode 1, invokes BIOS SWI 0x25, and returns the result in r0. Pinned libagbsyscall sources corroborate the symbol and calling convention. No ROM bytes are published.\n",encoding="utf-8",newline="\n")
 test_path=Path("tests/test_multiboot_stub_disassembly.py");outputs=[catalog_path,source_path,summary_path,*maps,research_path,test_path];missing=[p.as_posix() for p in outputs if not(root/p).is_file()]
 if missing:raise ValueError("missing output(s): "+", ".join(missing))
 common.write_json(root/"manifests/multiboot-stub-disassembly.json",{"schema_version":1,"axis":"Disassembly","game":game,"library":"libagbsyscall","function":"MultiBoot","profile":family,"origin_reference":releases[0]["id"],"release_count":len(records),"generator":{"repository":"SakuraiTsubaki/Disassembly","tool":"tools/catalog_gen3_multiboot_stub.py","tool_sha256":common.file_hash(Path(__file__))},"outputs":[{"path":p.as_posix(),"sha256":common.file_hash(root/p)} for p in outputs],"raw_rom_bytes_included":False});return summary

def main()->int:
 p=argparse.ArgumentParser(description=__doc__);p.add_argument("--root",type=Path,required=True);p.add_argument("--rom-dir",type=Path,required=True);p.add_argument("--game",required=True);p.add_argument("--family",choices=sorted(LZ_RELATIVE),required=True);a=p.parse_args()
 try:build(a.root,a.rom_dir,a.game,a.family)
 except(OSError,KeyError,ValueError,json.JSONDecodeError) as e:p.error(str(e))
 return 0
if __name__=="__main__":raise SystemExit(main())
