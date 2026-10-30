#!/usr/bin/env python3
"""Catalog the adjacent RegisterRamReset and SoftReset SDK stubs in Gen III ROMs."""
from __future__ import annotations
import argparse,csv,hashlib,json
from pathlib import Path

REGISTER_LENGTH=4
SOFT_RESET_LENGTH=24
SUITE_LENGTH=28
REGISTER_SIGNATURE=bytes.fromhex("01df7047")
SOFT_RESET_SIGNATURE=bytes.fromhex("034b00221a7003498d4601df00df000008020004007f0003")
SUITE_SIGNATURE=REGISTER_SIGNATURE+SOFT_RESET_SIGNATURE
PROFILES={
 "rs":{"repository":"pret/pokeruby","commit":"5784633ce4ef7ade1a7f2d2d0c288e3d5e6cdd7f","path":"src/main.c"},
 "emerald":{"repository":"pret/pokeemerald","commit":"fe1d8e51b265851676b65885818b1f5f62586135","path":"src/main.c"},
 "frlg":{"repository":"pret/pokefirered","commit":"037335f4c725d7c9aecdac87066f2002b4bd7e14","path":"src/main.c"}}
ROM_BASE=0x08000000
def digest(data:bytes)->str:return hashlib.sha256(data).hexdigest()
def file_hash(path:Path)->str:return digest(path.read_bytes())
def write_json(path:Path,value:object)->None:path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value,indent=2)+"\n",encoding="utf-8",newline="\n")
def rom_index(directory:Path)->dict[str,Path]:
 out={}
 for p in directory.iterdir():
  if p.is_file() and p.suffix.lower()==".gba":out.setdefault(file_hash(p),p)
 return out
def load_releases(path:Path)->list[dict[str,str]]:
 with path.open(encoding="utf-8",newline="")as f:items=list(csv.DictReader(f))
 if not items or items[0]["language"]!="Japanese":raise ValueError("release catalog must begin with Japanese origin")
 return items
def locate(data:bytes)->list[int]:
 found=[];start=0
 while True:
  start=data.find(SUITE_SIGNATURE,start)
  if start<0:return found
  found.append(start);start+=1
def source_text()->str:
 return '''.syntax unified
.thumb

.global RegisterRamReset
.type RegisterRamReset, %function
RegisterRamReset:
    swi 1
    bx lr
.size RegisterRamReset, . - RegisterRamReset

.global SoftReset
.type SoftReset, %function
SoftReset:
    ldr r3, .LRegIme
    movs r2, #0
    strb r2, [r3]
    ldr r1, .LResetStack
    mov sp, r1
    swi 1
    swi 0
    .align 2
.LRegIme:
    .word 0x04000208
.LResetStack:
    .word 0x03007F00
.size SoftReset, . - SoftReset
'''
def build(root:Path,rom_dir:Path,game:str,family:str)->dict:
 profile=PROFILES[family];catalog_path=Path("research/releases.csv");releases=load_releases(root/catalog_path);source_path=Path("src/reset_stubs.s");(root/source_path).write_text(source_text(),encoding="utf-8",newline="\n");roms=rom_index(rom_dir);maps=[];records=[]
 for index,release in enumerate(releases):
  rid,sha256=release["id"],release["sha256"]
  if sha256 not in roms:raise ValueError(f"missing catalog ROM: {rid}")
  data=roms[sha256].read_bytes();matches=locate(data)
  if len(matches)!=1:raise ValueError(f"expected one reset stub suite in {rid}, found {len(matches)}")
  start=matches[0];soft=start+REGISTER_LENGTH;end=start+SUITE_LENGTH
  evidence={"schema_version":1,"axis":"Disassembly","profile":family,"target":{"release":rid,"sha256":sha256,"status":release.get("status","candidate")},"origin_reference":index==0,"source":source_path.as_posix(),"source_sha256":file_hash(root/source_path),
   "functions":{"RegisterRamReset":{"rom_offset":start,"address":f"0x{ROM_BASE+start:08X}","range_end_exclusive":f"0x{ROM_BASE+soft:08X}","length":REGISTER_LENGTH,"code_sha256":digest(data[start:soft]),"software_interrupt":1,"return":"bx lr"},"SoftReset":{"rom_offset":soft,"address":f"0x{ROM_BASE+soft:08X}","range_end_exclusive":f"0x{ROM_BASE+end:08X}","length":SOFT_RESET_LENGTH,"code_sha256":digest(data[soft:end]),"interrupt_master_enable_address":"0x04000208","reset_stack_pointer":"0x03007F00","register_ram_reset_swi":1,"soft_reset_swi":0,"nonreturning":True}},
   "verified_layout":{"adjacent":True,"suite_length":SUITE_LENGTH,"register_to_soft_reset_delta":REGISTER_LENGTH},"naming_basis":profile,"raw_rom_bytes_included":False}
  map_path=Path(f"analysis/{rid}-reset-stubs.json");write_json(root/map_path,evidence);maps.append(map_path)
  records.append({"id":rid,"language":release["language"],"revision":int(release["revision"]),"status":release.get("status","candidate"),"sha256":sha256,"origin_reference":index==0,"register_ram_reset_address":evidence["functions"]["RegisterRamReset"]["address"],"soft_reset_address":evidence["functions"]["SoftReset"]["address"],"suite_sha256":digest(data[start:end]),"evidence":map_path.as_posix()})
 summary={"schema_version":1,"axis":"Disassembly","game":game,"functions":["RegisterRamReset","SoftReset"],"profile":family,"origin_reference":releases[0]["id"],"release_count":len(records),"source":source_path.as_posix(),"releases":records,"raw_rom_bytes_included":False};summary_path=Path("analysis/reset-stubs-summary.json");write_json(root/summary_path,summary)
 languages=", ".join(dict.fromkeys(x["language"]for x in records));research_path=Path("research/reset-stubs-disassembly.md");(root/research_path).write_text(f"# {game} reset SDK stubs disassembly\n\n`{releases[0]['id']}` is the Japanese origin reference. All {len(records)} cataloged releases ({languages}) contain exactly one adjacent RegisterRamReset/SoftReset suite. RegisterRamReset invokes SWI 1 and returns. SoftReset disables REG_IME, moves SP to 0x03007F00, invokes SWI 1 with flags in r0, and performs non-returning SWI 0. Per-release maps record decoded operands, layout and hashes without ROM bytes.\n",encoding="utf-8",newline="\n")
 test_path=Path("tests/test_reset_stubs_disassembly.py");outputs=[catalog_path,source_path,summary_path,*maps,research_path,test_path];missing=[p.as_posix()for p in outputs if not(root/p).is_file()]
 if missing:raise ValueError("missing output(s): "+", ".join(missing))
 write_json(root/"manifests/reset-stubs-disassembly.json",{"schema_version":1,"axis":"Disassembly","game":game,"functions":summary["functions"],"profile":family,"origin_reference":releases[0]["id"],"release_count":len(records),"generator":{"repository":"SakuraiTsubaki/Disassembly","tool":"tools/catalog_gen3_reset_stubs.py","tool_sha256":file_hash(Path(__file__))},"outputs":[{"path":p.as_posix(),"sha256":file_hash(root/p)}for p in outputs],"raw_rom_bytes_included":False})
 return summary
def main()->int:
 p=argparse.ArgumentParser(description=__doc__);p.add_argument("--root",type=Path,required=True);p.add_argument("--rom-dir",type=Path,required=True);p.add_argument("--game",required=True);p.add_argument("--family",choices=sorted(PROFILES),required=True);a=p.parse_args()
 try:build(a.root,a.rom_dir,a.game,a.family)
 except(OSError,KeyError,ValueError,json.JSONDecodeError)as e:p.error(str(e))
 return 0
if __name__=="__main__":raise SystemExit(main())

