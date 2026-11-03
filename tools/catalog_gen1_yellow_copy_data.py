#!/usr/bin/env python3
"""Correctly reconstruct Yellow's chunked home-bank CopyData routine."""
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import catalog_gen1_clear_screen as common
LENGTH=23
PROFILE={"repository":"pret/pokeyellow","commit":"31b7c2ea2ba6c8c64ed083723fbaa8cbb74669cb","path":"home/copy.asm"}
def decode(data:bytes,offset:int)->dict|None:
 c=data[offset:offset+LENGTH]
 if len(c)!=LENGTH or c[:3]!=bytes.fromhex("78a728") or c[3]!=12 or c[4:7]!=bytes.fromhex("79a728") or c[7]!=1 or c[8]!=4 or c[9]!=0xCD or c[12:16]!=bytes.fromhex("0520fac9") or c[16:]!=bytes.fromhex("2a12130d20fac9"):return None
 bank=offset//0x4000;address=offset if bank==0 else 0x4000+offset%0x4000;helper=c[10]|c[11]<<8
 if helper!=address+16:return None
 return {"rom_offset":offset,"bank":bank,"address":address,"range_end_exclusive":offset+LENGTH,"length":LENGTH,"code_sha256":common.digest(c),"copybytes_address":helper}
def locate(data:bytes)->list[dict]:
 return [f for o in range(min(0x4000,len(data))-LENGTH+1) if (f:=decode(data,o)) is not None]
def source_text()->str:
 return """SECTION "CopyData Reconstruction", ROM0

CopyData::
    ld a, b
    and a
    jr z, .copybytes
    ld a, c
    and a
    jr z, .loop
    inc b
.loop
    call .copybytes
    dec b
    jr nz, .loop
    ret
.copybytes
    ld a, [hli]
    ld [de], a
    inc de
    dec c
    jr nz, .copybytes
    ret
"""
def build(root:Path,rom_dir:Path,game:str)->dict:
 catalog_path,releases=common.load_releases(root);roms=common.rom_index(rom_dir);source_path=Path("src/copy_data.asm");(root/source_path).write_text(source_text(),encoding="utf-8",newline="\n");maps=[];records=[]
 for index,release in enumerate(releases):
  rid,sha256=release["id"],release["sha256"]
  if sha256 not in roms:raise ValueError(f"missing release ROM: {rid}")
  data=roms[sha256].read_bytes();matches=locate(data)
  if len(matches)!=1:raise ValueError(f"expected one Yellow CopyData in {rid}, found {len(matches)}")
  f=matches[0];evidence={"schema_version":1,"target":{"release":rid,"sha256":sha256,"status":release.get("status","candidate")},"origin_reference":index==0,"function":{"name":"CopyData",**f},"semantics":{"source":"HL","destination":"DE","length":"BC","operation":"copy BC bytes in C-sized chunks while B counts high-byte iterations","zero_length_precondition":"BC must be nonzero; zero would wrap the low-byte loop","return_registers":"HL and DE point one byte past their ranges; BC is zero"},"naming_basis":PROFILE,"raw_rom_bytes_included":False}
  map_path=Path(f"analysis/{rid}-copy-data.json");common.write_json(root/map_path,evidence);maps.append(map_path);records.append({"id":rid,"language":release.get("language",common.infer_language(rid)),"revision":int(release.get("revision",0)),"status":release.get("status","candidate"),"sha256":sha256,"origin_reference":index==0,"bank":f["bank"],"address":f"0x{f['address']:04X}","evidence":map_path.as_posix()})
 summary={"schema_version":1,"game":game,"function":"CopyData","profile":"yellow","origin_reference":releases[0]["id"],"release_count":len(records),"source":source_path.as_posix(),"releases":records,"raw_rom_bytes_included":False};summary_path=Path("analysis/copy-data-summary.json");common.write_json(root/summary_path,summary)
 languages=", ".join(dict.fromkeys(x["language"] for x in records));research_path=Path("research/copy-data-reconstruction.md");(root/research_path).write_text(f"# {game} CopyData reconstruction\n\n{releases[0]['id']} is the Japanese origin reference. All {len(records)} cataloged Yellow releases ({languages}) independently verify the actual 23-byte home-bank CopyData implementation from pokeyellow. It handles the 16-bit BC length in C-sized chunks and is distinct from the unrelated Red-style nine-byte loop in bank 0x3E. Reports preserve identities, addresses, semantics, and hashes without ROM bytes.\n",encoding="utf-8",newline="\n")
 test_path=Path("tests/test_copy_data_reconstruction.py");outputs=[catalog_path,source_path,summary_path,*maps,research_path,test_path]
 common.write_json(root/"manifests/copy-data-reconstruction.json",{"schema_version":1,"game":game,"function":"CopyData","profile":"yellow","origin_reference":releases[0]["id"],"release_count":len(records),"generator":{"repository":"SakuraiTsubaki/Disassembly","tool":"tools/catalog_gen1_yellow_copy_data.py","tool_sha256":common.file_hash(Path(__file__))},"outputs":[{"path":p.as_posix(),"sha256":common.file_hash(root/p)} for p in outputs],"raw_rom_bytes_included":False});return summary
def main()->int:
 p=argparse.ArgumentParser(description=__doc__);p.add_argument("--root",type=Path,required=True);p.add_argument("--rom-dir",type=Path,required=True);p.add_argument("--game",default="Pikachu");a=p.parse_args()
 try:build(a.root,a.rom_dir,a.game)
 except(OSError,KeyError,ValueError,json.JSONDecodeError) as e:p.error(str(e))
 return 0
if __name__=="__main__":raise SystemExit(main())
