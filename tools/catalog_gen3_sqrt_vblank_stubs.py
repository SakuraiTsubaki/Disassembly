#!/usr/bin/env python3
"""Catalog adjacent Sqrt and VBlankIntrWait BIOS stubs in Gen III ROMs."""
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import catalog_gen3_reset_stubs as common

SQRT_LENGTH=4
VBLANK_LENGTH=6
SUITE_LENGTH=10
RESET_TO_SUITE_DELTA=28
SQRT_SIGNATURE=bytes.fromhex("08df7047")
VBLANK_SIGNATURE=bytes.fromhex("002205df7047")
SUITE_SIGNATURE=SQRT_SIGNATURE+VBLANK_SIGNATURE
def locate(data:bytes)->list[int]:
 out=[];start=0
 while True:
  start=data.find(SUITE_SIGNATURE,start)
  if start<0:return out
  out.append(start);start+=1
def source_text()->str:
 return '''.syntax unified
.thumb

.global Sqrt
.type Sqrt, %function
Sqrt:
    swi 8
    bx lr
.size Sqrt, . - Sqrt

.global VBlankIntrWait
.type VBlankIntrWait, %function
VBlankIntrWait:
    movs r2, #0
    swi 5
    bx lr
.size VBlankIntrWait, . - VBlankIntrWait
'''
def build(root:Path,rom_dir:Path,game:str,family:str)->dict:
 profile=common.PROFILES[family];catalog_path=Path("research/releases.csv");releases=common.load_releases(root/catalog_path);source_path=Path("src/sqrt_vblank_stubs.s");(root/source_path).write_text(source_text(),encoding="utf-8",newline="\n");roms=common.rom_index(rom_dir);maps=[];records=[]
 for index,release in enumerate(releases):
  rid,sha256=release["id"],release["sha256"]
  if sha256 not in roms:raise ValueError(f"missing catalog ROM: {rid}")
  reset_path=Path(f"analysis/{rid}-reset-stubs.json");reset=json.loads((root/reset_path).read_text(encoding="utf-8"));reset_start=reset["functions"]["RegisterRamReset"]["rom_offset"]
  data=roms[sha256].read_bytes();matches=locate(data)
  if len(matches)!=1:raise ValueError(f"expected one sqrt/vblank stub suite in {rid}, found {len(matches)}")
  start=matches[0]
  if start-reset_start!=RESET_TO_SUITE_DELTA:raise ValueError(f"SDK stub suite layout differs: {rid}")
  vblank=start+SQRT_LENGTH;end=start+SUITE_LENGTH
  evidence={"schema_version":1,"axis":"Disassembly","profile":family,"target":{"release":rid,"sha256":sha256,"status":release.get("status","candidate")},"origin_reference":index==0,"source":source_path.as_posix(),"source_sha256":common.file_hash(root/source_path),
   "functions":{"Sqrt":{"rom_offset":start,"address":f"0x{common.ROM_BASE+start:08X}","range_end_exclusive":f"0x{common.ROM_BASE+vblank:08X}","length":SQRT_LENGTH,"code_sha256":common.digest(data[start:vblank]),"software_interrupt":8,"return":"bx lr","argument_register":"r0","result_register":"r0"},"VBlankIntrWait":{"rom_offset":vblank,"address":f"0x{common.ROM_BASE+vblank:08X}","range_end_exclusive":f"0x{common.ROM_BASE+end:08X}","length":VBLANK_LENGTH,"code_sha256":common.digest(data[vblank:end]),"temporary_register":"r2","temporary_value":0,"software_interrupt":5,"return":"bx lr"}},
   "verified_layout":{"adjacent":True,"suite_length":SUITE_LENGTH,"reset_suite_to_sqrt_delta":RESET_TO_SUITE_DELTA},"cross_reference":{"reset_stubs_map":reset_path.as_posix(),"reset_stubs_map_sha256":common.file_hash(root/reset_path)},"naming_basis":profile,"raw_rom_bytes_included":False}
  map_path=Path(f"analysis/{rid}-sqrt-vblank-stubs.json");common.write_json(root/map_path,evidence);maps.append(map_path)
  records.append({"id":rid,"language":release["language"],"revision":int(release["revision"]),"status":release.get("status","candidate"),"sha256":sha256,"origin_reference":index==0,"sqrt_address":evidence["functions"]["Sqrt"]["address"],"vblank_intr_wait_address":evidence["functions"]["VBlankIntrWait"]["address"],"suite_sha256":common.digest(data[start:end]),"evidence":map_path.as_posix()})
 summary={"schema_version":1,"axis":"Disassembly","game":game,"functions":["Sqrt","VBlankIntrWait"],"profile":family,"origin_reference":releases[0]["id"],"release_count":len(records),"source":source_path.as_posix(),"releases":records,"raw_rom_bytes_included":False};summary_path=Path("analysis/sqrt-vblank-stubs-summary.json");common.write_json(root/summary_path,summary)
 languages=", ".join(dict.fromkeys(x["language"]for x in records));research_path=Path("research/sqrt-vblank-stubs-disassembly.md");(root/research_path).write_text(f"# {game} Sqrt and VBlankIntrWait SDK stubs\n\n`{releases[0]['id']}` is the Japanese origin reference. All {len(records)} cataloged releases ({languages}) contain exactly one adjacent Sqrt/VBlankIntrWait suite at a fixed +28-byte displacement from the verified reset-stub suite. Sqrt invokes BIOS SWI 8. VBlankIntrWait clears r2, invokes BIOS SWI 5, and returns. Stub presence is recorded independently of whether a game's main loop calls it; Ruby/Sapphire use the call while Emerald/FRLG poll VBlank state directly. No ROM bytes are published.\n",encoding="utf-8",newline="\n")
 test_path=Path("tests/test_sqrt_vblank_stubs_disassembly.py");outputs=[catalog_path,source_path,summary_path,*maps,research_path,test_path];missing=[p.as_posix()for p in outputs if not(root/p).is_file()]
 if missing:raise ValueError("missing output(s): "+", ".join(missing))
 common.write_json(root/"manifests/sqrt-vblank-stubs-disassembly.json",{"schema_version":1,"axis":"Disassembly","game":game,"functions":summary["functions"],"profile":family,"origin_reference":releases[0]["id"],"release_count":len(records),"generator":{"repository":"SakuraiTsubaki/Disassembly","tool":"tools/catalog_gen3_sqrt_vblank_stubs.py","tool_sha256":common.file_hash(Path(__file__))},"outputs":[{"path":p.as_posix(),"sha256":common.file_hash(root/p)}for p in outputs],"raw_rom_bytes_included":False})
 return summary
def main()->int:
 p=argparse.ArgumentParser(description=__doc__);p.add_argument("--root",type=Path,required=True);p.add_argument("--rom-dir",type=Path,required=True);p.add_argument("--game",required=True);p.add_argument("--family",choices=sorted(common.PROFILES),required=True);a=p.parse_args()
 try:build(a.root,a.rom_dir,a.game,a.family)
 except(OSError,KeyError,ValueError,json.JSONDecodeError)as e:p.error(str(e))
 return 0
if __name__=="__main__":raise SystemExit(main())
