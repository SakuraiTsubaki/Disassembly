#!/usr/bin/env python3
"""Catalog the libgcc Thumb _call_via_rX trampoline suite in Gen III ROMs."""
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import catalog_gen3_reset_stubs as common

FUNCTIONS=[*( (f"_call_via_r{i}",f"r{i}",i) for i in range(10)),("_call_via_sl","sl",10),("_call_via_fp","fp",11),("_call_via_ip","ip",12),("_call_via_sp","sp",13),("_call_via_lr","lr",14)]
FUNCTION_LENGTH=4
VBLANK_END_TO_SUITE_DELTA=2
ALIGNMENT_PADDING=bytes.fromhex("0000")
NOP=bytes.fromhex("c046")
def encoding(register:int)->bytes:return (0x4700+(register<<3)).to_bytes(2,"little")+NOP
SUITE_SIGNATURE=b"".join(encoding(register)for _,_,register in FUNCTIONS)
SUITE_LENGTH=len(SUITE_SIGNATURE)
LINKER_PATHS={"rs":"ld_script.txt","emerald":"ld_script.ld","frlg":"ld_script.ld"}
def locate(data:bytes)->list[int]:
 out=[];start=0
 while True:
  start=data.find(SUITE_SIGNATURE,start)
  if start<0:return out
  out.append(start);start+=1
def source_text()->str:
 lines=[".syntax unified",".thumb","",".balign 4, 0"]
 for name,register,_ in FUNCTIONS:lines += [f".global {name}",f".type {name}, %function",f"{name}:",f"    bx {register}","    nop",f".size {name}, . - {name}",""]
 return "\n".join(lines)
def build(root:Path,rom_dir:Path,game:str,family:str)->dict:
 profile=common.PROFILES[family];catalog_path=Path("research/releases.csv");releases=common.load_releases(root/catalog_path);source_path=Path("src/call_via_stubs.s");(root/source_path).write_text(source_text(),encoding="utf-8",newline="\n");roms=common.rom_index(rom_dir);maps=[];records=[]
 for index,release in enumerate(releases):
  rid,sha256=release["id"],release["sha256"]
  if sha256 not in roms:raise ValueError(f"missing catalog ROM: {rid}")
  prior_path=Path(f"analysis/{rid}-sqrt-vblank-stubs.json");prior=json.loads((root/prior_path).read_text(encoding="utf-8"));vblank=prior["functions"]["VBlankIntrWait"];vblank_end=int(vblank["rom_offset"])+int(vblank["length"])
  data=roms[sha256].read_bytes();matches=locate(data);start=vblank_end+VBLANK_END_TO_SUITE_DELTA
  if start not in matches:raise ValueError(f"missing call-via suite at verified adjacent position: {rid}")
  if start-vblank_end!=VBLANK_END_TO_SUITE_DELTA or data[vblank_end:start]!=ALIGNMENT_PADDING:raise ValueError(f"call-via alignment differs: {rid}")
  functions={}
  for ordinal,(name,register,number) in enumerate(FUNCTIONS):
   offset=start+ordinal*FUNCTION_LENGTH;chunk=data[offset:offset+FUNCTION_LENGTH]
   if chunk!=encoding(number):raise ValueError(f"call-via encoding differs: {rid} {name}")
   functions[name]={"rom_offset":offset,"address":f"0x{common.ROM_BASE+offset:08X}","range_end_exclusive":f"0x{common.ROM_BASE+offset+FUNCTION_LENGTH:08X}","length":FUNCTION_LENGTH,"code_sha256":common.digest(chunk),"branch_exchange_register":register,"register_number":number,"trailing_instruction":"nop"}
  evidence={"schema_version":1,"axis":"Disassembly","profile":family,"target":{"release":rid,"sha256":sha256,"status":release.get("status","candidate")},"origin_reference":index==0,"source":source_path.as_posix(),"source_sha256":common.file_hash(root/source_path),"functions":functions,"verified_layout":{"function_count":len(FUNCTIONS),"suite_length":SUITE_LENGTH,"word_aligned":start%4==0,"vblank_end_to_suite_delta":VBLANK_END_TO_SUITE_DELTA,"alignment_padding_sha256":common.digest(ALIGNMENT_PADDING),"suite_signature_match_count":len(matches),"selected_by_verified_adjacency":True},"cross_reference":{"sqrt_vblank_map":prior_path.as_posix(),"sqrt_vblank_map_sha256":common.file_hash(root/prior_path)},"naming_basis":{**profile,"path":LINKER_PATHS[family],"section_pattern":"libgcc.a:_call_via_rX.o(.text)"},"raw_rom_bytes_included":False}
  map_path=Path(f"analysis/{rid}-call-via-stubs.json");common.write_json(root/map_path,evidence);maps.append(map_path);records.append({"id":rid,"language":release["language"],"revision":int(release["revision"]),"status":release.get("status","candidate"),"sha256":sha256,"origin_reference":index==0,"suite_address":f"0x{common.ROM_BASE+start:08X}","suite_sha256":common.digest(data[start:start+SUITE_LENGTH]),"signature_match_count":len(matches),"evidence":map_path.as_posix()})
 summary={"schema_version":1,"axis":"Disassembly","game":game,"library":"libgcc","object":"_call_via_rX.o","profile":family,"origin_reference":releases[0]["id"],"release_count":len(records),"function_count":len(FUNCTIONS),"functions":[x[0]for x in FUNCTIONS],"source":source_path.as_posix(),"releases":records,"raw_rom_bytes_included":False};summary_path=Path("analysis/call-via-stubs-summary.json");common.write_json(root/summary_path,summary)
 languages=", ".join(dict.fromkeys(x["language"]for x in records));duplicates=sum(x["signature_match_count"]>1 for x in records);research_path=Path("research/call-via-stubs-disassembly.md");(root/research_path).write_text(f"# {game} libgcc call-via trampolines\n\n`{releases[0]['id']}` is the Japanese origin reference. All {len(records)} cataloged releases ({languages}) contain the same word-aligned `_call_via_rX` suite immediately after the verified BIOS stubs. The suite provides 15 four-byte Thumb trampolines for r0-r9, sl, fp, ip, sp, and lr; each executes `bx` through its named register followed by a padding `nop`. The pinned upstream linker script places `libgcc.a:_call_via_rX.o(.text)` here. {duplicates} release(s) also contain a second byte-identical suite elsewhere, so the selected instance is anchored by its verified adjacency rather than global signature uniqueness. No ROM bytes are published.\n",encoding="utf-8",newline="\n")
 test_path=Path("tests/test_call_via_stubs_disassembly.py");outputs=[catalog_path,source_path,summary_path,*maps,research_path,test_path];missing=[p.as_posix()for p in outputs if not(root/p).is_file()]
 if missing:raise ValueError("missing output(s): "+", ".join(missing))
 common.write_json(root/"manifests/call-via-stubs-disassembly.json",{"schema_version":1,"axis":"Disassembly","game":game,"library":"libgcc","object":"_call_via_rX.o","profile":family,"origin_reference":releases[0]["id"],"release_count":len(records),"function_count":len(FUNCTIONS),"generator":{"repository":"SakuraiTsubaki/Disassembly","tool":"tools/catalog_gen3_call_via_stubs.py","tool_sha256":common.file_hash(Path(__file__))},"outputs":[{"path":p.as_posix(),"sha256":common.file_hash(root/p)}for p in outputs],"raw_rom_bytes_included":False})
 return summary
def main()->int:
 p=argparse.ArgumentParser(description=__doc__);p.add_argument("--root",type=Path,required=True);p.add_argument("--rom-dir",type=Path,required=True);p.add_argument("--game",required=True);p.add_argument("--family",choices=sorted(common.PROFILES),required=True);a=p.parse_args()
 try:build(a.root,a.rom_dir,a.game,a.family)
 except(OSError,KeyError,ValueError,json.JSONDecodeError)as e:p.error(str(e))
 return 0
if __name__=="__main__":raise SystemExit(main())
