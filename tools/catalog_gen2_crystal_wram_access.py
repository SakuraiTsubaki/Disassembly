#!/usr/bin/env python3
"""Catalog Crystal's banked-WRAM copy and read helpers."""
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import catalog_gen1_clear_screen as common
LENGTHS={"FarCopyWRAM":16,"GetFarWRAMByte":18,"GetFarWRAMWord":16}
SUITE_LENGTH=sum(LENGTHS.values())
PROFILE={"repository":"pret/pokecrystal","commit":"3bc8daa4173e96a7f4011dad3922eb6fa5dad5c6","path":"home/copy.asm"}
def decode(data:bytes,offset:int,copy_bytes_address:int)->dict|None:
 c=data[offset:offset+SUITE_LENGTH]
 if len(c)!=SUITE_LENGTH:return None
 a=c[:16];b=c[16:34];w=c[34:50]
 if not(a[0]==0xE0 and a[2]==0xF0 and a[4]==0xF5 and a[5]==0xF0 and a[7]==0xE0 and a[9]==0xCD and a[12]==0xF1 and a[13]==0xE0 and a[15]==0xC9):return None
 if int.from_bytes(a[10:12],"little")!=copy_bytes_address or not(a[1]==a[6] and a[3]==a[8] and a[3]==a[14]):return None
 if not(b[0]==0xE0 and b[2]==0xF0 and b[4]==0xF5 and b[5]==0xF0 and b[7]==0xE0 and b[9]==0x7E and b[10]==0xE0 and b[12]==0xF1 and b[13]==0xE0 and b[15]==0xF0 and b[17]==0xC9):return None
 if not(b[1]==b[6] and b[1]==b[11] and b[1]==b[16] and b[3]==b[8] and b[3]==b[14]):return None
 if not(w[0]==0xE0 and w[2]==0xF0 and w[4]==0xF5 and w[5]==0xF0 and w[7]==0xE0 and w[9:12]==bytes.fromhex("2a666f") and w[12]==0xF1 and w[13]==0xE0 and w[15]==0xC9):return None
 if not(w[1]==w[6] and w[3]==w[8] and w[3]==w[14]):return None
 if not(a[1]==b[1] and a[1]==w[1] and a[3]==b[3] and a[3]==w[3]):return None
 return {"hTempBank":f"0xFF{a[1]:02X}","rWBK":f"0xFF{a[3]:02X}","hFarByte":f"0xFF{b[11]:02X}","codes":{"FarCopyWRAM":a,"GetFarWRAMByte":b,"GetFarWRAMWord":w}}
def source_text()->str:
 return """SECTION "Banked WRAM Access Reconstruction", ROM0

FarCopyWRAM::
    ldh [hTempBank], a
    ldh a, [rWBK]
    push af
    ldh a, [hTempBank]
    ldh [rWBK], a
    call CopyBytes
    pop af
    ldh [rWBK], a
    ret

GetFarWRAMByte::
    ldh [hTempBank], a
    ldh a, [rWBK]
    push af
    ldh a, [hTempBank]
    ldh [rWBK], a
    ld a, [hl]
    ldh [hFarByte], a
    pop af
    ldh [rWBK], a
    ldh a, [hFarByte]
    ret

GetFarWRAMWord::
    ldh [hTempBank], a
    ldh a, [rWBK]
    push af
    ldh a, [hTempBank]
    ldh [rWBK], a
    ld a, [hli]
    ld h, [hl]
    ld l, a
    pop af
    ldh [rWBK], a
    ret
"""
def build(root:Path,rom_dir:Path,game:str)->dict:
 catalog_path,releases=common.load_releases(root);roms=common.rom_index(rom_dir);source_path=Path("src/wram_access.asm");(root/source_path).write_text(source_text(),encoding="utf-8",newline="\n");maps=[];records=[]
 for index,release in enumerate(releases):
  rid,sha256=release["id"],release["sha256"]
  if sha256 not in roms:raise ValueError(f"missing release ROM: {rid}")
  dep_path=Path(f"analysis/{rid}-far-access.json");dep=json.loads((root/dep_path).read_text(encoding="utf-8"));start=int(dep["functions"]["GetFarWord"]["range_end_exclusive"])
  copy_path=Path(f"analysis/{rid}-copy-bytes.json");copy=json.loads((root/copy_path).read_text(encoding="utf-8"));data=roms[sha256].read_bytes();decoded=decode(data,start,int(copy["function"]["address"]))
  if decoded is None:raise ValueError(f"WRAM access suite differs in {rid}")
  functions={};cursor=start
  for name,length in LENGTHS.items():
   code=decoded["codes"][name];functions[name]={"rom_offset":cursor,"bank":0,"address":cursor,"range_end_exclusive":cursor+length,"length":length,"code_sha256":common.digest(code)};cursor+=length
  evidence={"schema_version":1,"target":{"release":rid,"sha256":sha256,"status":release.get("status","candidate")},"origin_reference":index==0,"functions":functions,"hardware":{"temporary_bank":decoded["hTempBank"],"wram_bank_register":decoded["rWBK"],"far_byte_storage":decoded["hFarByte"]},"semantics":{"FarCopyWRAM":"copy BC bytes from HL to DE while temporarily selecting WRAM bank A","GetFarWRAMByte":"read [HL] from WRAM bank A and return it in A","GetFarWRAMWord":"read little-endian [HL:HL+1] from WRAM bank A and return it in HL"},"cross_reference":{"far_access":dep_path.as_posix(),"far_access_sha256":common.file_hash(root/dep_path),"copy_bytes":copy_path.as_posix(),"copy_bytes_sha256":common.file_hash(root/copy_path),"adjacent_to_get_far_word":True},"naming_basis":PROFILE,"raw_rom_bytes_included":False}
  map_path=Path(f"analysis/{rid}-wram-access.json");common.write_json(root/map_path,evidence);maps.append(map_path);language=release["language"] if release.get("language") else common.infer_language(rid);records.append({"id":rid,"language":language,"revision":int(release.get("revision",0)),"status":release.get("status","candidate"),"sha256":sha256,"origin_reference":index==0,"addresses":{n:f"0x{f['address']:04X}" for n,f in functions.items()},"evidence":map_path.as_posix()})
 summary={"schema_version":1,"game":game,"functions":list(LENGTHS),"profile":"crystal","origin_reference":releases[0]["id"],"release_count":len(records),"source":source_path.as_posix(),"releases":records,"raw_rom_bytes_included":False};summary_path=Path("analysis/wram-access-summary.json");common.write_json(root/summary_path,summary)
 languages=", ".join(dict.fromkeys(x["language"] for x in records));research_path=Path("research/wram-access-reconstruction.md");(root/research_path).write_text(f"# {game} banked-WRAM access reconstruction\n\n{releases[0]['id']} is the Japanese origin reference. All {len(records)} cataloged Crystal releases ({languages}) verify the adjacent FarCopyWRAM, GetFarWRAMByte, and GetFarWRAMWord suite immediately after GetFarWord. Each helper saves and restores rWBK while selecting bank A. Gold and Silver do not receive synthetic copies of this Crystal-specific suite. No ROM bytes are published.\n",encoding="utf-8",newline="\n")
 test_path=Path("tests/test_wram_access_reconstruction.py");outputs=[catalog_path,source_path,summary_path,*maps,research_path,test_path]
 common.write_json(root/"manifests/wram-access-reconstruction.json",{"schema_version":1,"game":game,"functions":list(LENGTHS),"profile":"crystal","origin_reference":releases[0]["id"],"release_count":len(records),"generator":{"repository":"SakuraiTsubaki/Disassembly","tool":"tools/catalog_gen2_crystal_wram_access.py","tool_sha256":common.file_hash(Path(__file__))},"outputs":[{"path":p.as_posix(),"sha256":common.file_hash(root/p)} for p in outputs],"raw_rom_bytes_included":False});return summary
def main()->int:
 p=argparse.ArgumentParser(description=__doc__);p.add_argument("--root",type=Path,required=True);p.add_argument("--rom-dir",type=Path,required=True);p.add_argument("--game",default="Crystal");a=p.parse_args()
 try:build(a.root,a.rom_dir,a.game)
 except(OSError,KeyError,ValueError,json.JSONDecodeError) as e:p.error(str(e))
 return 0
if __name__=="__main__":raise SystemExit(main())
