#!/usr/bin/env python3
"""Catalog Crystal's SwapBytes routine from the verified CopyBytes boundary."""
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import catalog_gen1_clear_screen as common
LENGTH=13
SIGNATURE=bytes.fromhex("7ef51a22f112130b78b120f4c9")
PROFILE={"repository":"pret/pokecrystal","commit":"3bc8daa4173e96a7f4011dad3922eb6fa5dad5c6","path":"home/copy.asm"}
def decode(data:bytes,offset:int)->dict|None:
 c=data[offset:offset+LENGTH]
 if c!=SIGNATURE:return None
 return {"rom_offset":offset,"bank":0,"address":offset,"range_end_exclusive":offset+LENGTH,"length":LENGTH,"code_sha256":common.digest(c)}
def source_text()->str:
 return """SECTION "SwapBytes Reconstruction", ROM0

SwapBytes::
.loop
    ld a, [hl]
    push af
    ld a, [de]
    ld [hli], a
    pop af
    ld [de], a
    inc de
    dec bc
    ld a, b
    or c
    jr nz, .loop
    ret
"""
def build(root:Path,rom_dir:Path,game:str)->dict:
 catalog_path,releases=common.load_releases(root);roms=common.rom_index(rom_dir);source_path=Path("src/swap_bytes.asm");(root/source_path).write_text(source_text(),encoding="utf-8",newline="\n");maps=[];records=[]
 for index,release in enumerate(releases):
  rid,sha256=release["id"],release["sha256"]
  if sha256 not in roms:raise ValueError(f"missing release ROM: {rid}")
  dep_path=Path(f"analysis/{rid}-copy-bytes.json");dep=json.loads((root/dep_path).read_text(encoding="utf-8"));offset=int(dep["function"]["range_end_exclusive"]);data=roms[sha256].read_bytes();f=decode(data,offset)
  if f is None:raise ValueError(f"SwapBytes boundary differs in {rid}")
  evidence={"schema_version":1,"target":{"release":rid,"sha256":sha256,"status":release.get("status","candidate")},"origin_reference":index==0,"function":{"name":"SwapBytes",**f},"semantics":{"left":"HL","right":"DE","length":"BC","operation":"exchange BC bytes in place while advancing HL and DE","zero_length_precondition":"BC must be nonzero"},"cross_reference":{"copy_bytes":dep_path.as_posix(),"sha256":common.file_hash(root/dep_path),"adjacent":True},"naming_basis":PROFILE,"raw_rom_bytes_included":False}
  map_path=Path(f"analysis/{rid}-swap-bytes.json");common.write_json(root/map_path,evidence);maps.append(map_path);language=release["language"] if release.get("language") else common.infer_language(rid);records.append({"id":rid,"language":language,"revision":int(release.get("revision",0)),"status":release.get("status","candidate"),"sha256":sha256,"origin_reference":index==0,"address":f"0x{offset:04X}","evidence":map_path.as_posix()})
 summary={"schema_version":1,"game":game,"function":"SwapBytes","profile":"crystal","origin_reference":releases[0]["id"],"release_count":len(records),"source":source_path.as_posix(),"releases":records,"raw_rom_bytes_included":False};summary_path=Path("analysis/swap-bytes-summary.json");common.write_json(root/summary_path,summary)
 languages=", ".join(dict.fromkeys(x["language"] for x in records));research_path=Path("research/swap-bytes-reconstruction.md");(root/research_path).write_text(f"# {game} SwapBytes reconstruction\n\n{releases[0]['id']} is the Japanese origin reference. All {len(records)} cataloged Crystal releases ({languages}) place the 13-byte SwapBytes routine immediately after CopyBytes. It exchanges BC bytes between HL and DE in place. Gold and Silver do not expose this Crystal-specific home routine, so they are not assigned synthetic evidence. No ROM bytes are published.\n",encoding="utf-8",newline="\n")
 test_path=Path("tests/test_swap_bytes_reconstruction.py");outputs=[catalog_path,source_path,summary_path,*maps,research_path,test_path]
 common.write_json(root/"manifests/swap-bytes-reconstruction.json",{"schema_version":1,"game":game,"function":"SwapBytes","profile":"crystal","origin_reference":releases[0]["id"],"release_count":len(records),"generator":{"repository":"SakuraiTsubaki/Disassembly","tool":"tools/catalog_gen2_crystal_swap_bytes.py","tool_sha256":common.file_hash(Path(__file__))},"outputs":[{"path":p.as_posix(),"sha256":common.file_hash(root/p)} for p in outputs],"raw_rom_bytes_included":False});return summary
def main()->int:
 p=argparse.ArgumentParser(description=__doc__);p.add_argument("--root",type=Path,required=True);p.add_argument("--rom-dir",type=Path,required=True);p.add_argument("--game",default="Crystal");a=p.parse_args()
 try:build(a.root,a.rom_dir,a.game)
 except(OSError,KeyError,ValueError,json.JSONDecodeError) as e:p.error(str(e))
 return 0
if __name__=="__main__":raise SystemExit(main())
