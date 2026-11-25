#!/usr/bin/env python3
"""Disassemble WaitForVBlank across Generation III release catalogs."""
from __future__ import annotations
import argparse, hashlib, json, struct, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import disassemble_thumb_cfg

ROM_BASE=0x08000000
INTR_CHECK_OFFSET=0x1C
VBLANK_CLEAR_MASK=0xFFFE
PROFILES={
 "rs":{"mode":"bios-call","length":22,"repository":"pret/pokeruby","commit":"5784633ce4ef7ade1a7f2d2d0c288e3d5e6cdd7f"},
 "emerald":{"mode":"volatile-poll","length":40,"repository":"pret/pokeemerald","commit":"fe1d8e51b265851676b65885818b1f5f62586135"},
 "frlg":{"mode":"volatile-poll","length":40,"repository":"pret/pokefirered","commit":"037335f4c725d7c9aecdac87066f2002b4bd7e14"},
}
def digest(data): return hashlib.sha256(data).hexdigest()
def file_hash(path): return digest(path.read_bytes())
def write_json(path,value):
 path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value,indent=2)+"\n",encoding="utf-8",newline="\n")
def rom_index(directory):
 result={}
 for path in directory.iterdir():
  if path.is_file() and path.suffix.lower()==".gba":result.setdefault(file_hash(path),path)
 return result
def sign_extend(value,bits):
 sign=1<<(bits-1);return(value^sign)-sign
def literal_offset(offset,halfword):return((offset+4)&~3)+(halfword&0xFF)*4
def ldr(value,register):return value&0xF800==0x4800 and(value>>8)&7==register
def half(value,load,register,base,byte_offset):
 opcode=0x8800 if load else 0x8000
 return value&0xF800==opcode and value&7==register and(value>>3)&7==base and((value>>6)&0x1F)*2==byte_offset
def ands(value,destination,source):return value&0xFFC0==0x4000 and value&7==destination and(value>>3)&7==source
def mov(value,register,immediate):return value&0xF800==0x2000 and(value>>8)&7==register and value&0xFF==immediate
def cmpi(value,register,immediate):return value&0xF800==0x2800 and(value>>8)&7==register and value&0xFF==immediate
def add3(value,destination,source,immediate):return value&0xFE00==0x1C00 and value&7==destination and(value>>3)&7==source and(value>>6)&7==immediate
def branch_target(offset,value):
 if value&0xF000!=0xD000 or value&0x0F00==0x0F00:return None
 return offset+4+(sign_extend(value&0xFF,8)<<1)
def bl(first,second):return first&0xF800==0xF000 and second&0xF800==0xF800
def semantic_variant(data,offset,variant):
 count=11 if variant=="bios-call" else 20
 if offset<0 or offset%2 or offset+count*2>len(data):return False
 w=struct.unpack_from(f"<{count}H",data,offset)
 base=all((w[0]==0xB500,ldr(w[1],1 if variant=="bios-call" else 2),half(w[2],True,2 if variant=="bios-call" else 1,1 if variant=="bios-call" else 2,INTR_CHECK_OFFSET),ldr(w[3],0),ands(w[4],0,2 if variant=="bios-call" else 1),half(w[5],True,2 if variant=="bios-call" else 1,1 if variant=="bios-call" else 2,INTR_CHECK_OFFSET),half(w[6],False,0,1 if variant=="bios-call" else 2,INTR_CHECK_OFFSET)))
 if variant=="bios-call":return base and bl(w[7],w[8]) and w[9:]==(0xBC01,0x4700)
 return base and all((half(w[7],True,1,2,INTR_CHECK_OFFSET),mov(w[8],0,1),ands(w[9],0,1),cmpi(w[10],0,0),branch_target(offset+22,w[11])==offset+36,mov(w[12],3,1),half(w[13],True,1,2,INTR_CHECK_OFFSET),add3(w[14],0,3,0),ands(w[15],0,1),cmpi(w[16],0,0),branch_target(offset+34,w[17])==offset+26,w[18:]==(0xBC01,0x4700)))
def unique_candidate(data,expected_mode):
 found=[];marker=struct.pack("<H",0xB500);offset=0
 while True:
  offset=data.find(marker,offset)
  if offset<0:break
  if offset%2==0 and semantic_variant(data,offset,expected_mode):
   length=22 if expected_mode=="bios-call" else 40;words=struct.unpack_from(f"<{length//2}H",data,offset);g_lit=literal_offset(offset+2,words[1]);mask_lit=literal_offset(offset+6,words[3])
   if max(g_lit,mask_lit)+4<=len(data):
    g_main=struct.unpack_from("<I",data,g_lit)[0];mask=struct.unpack_from("<I",data,mask_lit)[0]
    if 0x03000000<=g_main<0x03008000 and mask==VBLANK_CLEAR_MASK:found.append((offset,g_main,g_lit,mask_lit))
  offset+=2
 if len(found)!=1:raise ValueError(f"expected one {expected_mode} WaitForVBlank candidate, found {len(found)}")
 return found[0]
def source_text(profile):
 if PROFILES[profile]["mode"]=="bios-call":
  body="""    ldr r1, =gMain
    ldrh r2, [r1, #28]
    ldr r0, =0x0000FFFE
    ands r0, r2
    strh r0, [r1, #28]
    bl VBlankIntrWait
"""
 else:
  body="""    ldr r2, =gMain
    ldrh r1, [r2, #28]
    ldr r0, =0x0000FFFE
    ands r0, r1
    strh r0, [r2, #28]
.LWaitSet:
    ldrh r1, [r2, #28]
    movs r0, #1
    ands r0, r1
    cmp r0, #0
    beq .LWaitSet
.LWaitClear:
    ldrh r1, [r2, #28]
    movs r3, #1
    adds r0, r3, #0
    ands r0, r1
    cmp r0, #0
    bne .LWaitClear
"""
 return """.syntax unified
.thumb

.global WaitForVBlank
.type WaitForVBlank, %function
WaitForVBlank:
    push {lr}
"""+body+"""    pop {r0}
    bx r0
.size WaitForVBlank, . - WaitForVBlank
"""
def build(root,rom_dir,catalog_path,game,profile):
 spec=PROFILES[profile];releases=json.loads((root/catalog_path).read_text(encoding="utf-8"))["releases"]
 if not releases or releases[0]["language"]!="Japanese":raise ValueError("catalog must begin with the Japanese origin release")
 source_path=Path("src/wait_for_vblank.s");(root/source_path).write_text(source_text(profile),encoding="utf-8",newline="\n");source_sha=file_hash(root/source_path);roms=rom_index(rom_dir);maps=[];records=[]
 for index,release in enumerate(releases):
  rid,sha=release["id"],release["sha256"]
  if sha not in roms:raise ValueError(f"missing catalog ROM: {rid}")
  data=roms[sha].read_bytes();offset,g_main,g_lit,mask_lit=unique_candidate(data,spec["mode"]);length=spec["length"];cfg=disassemble_thumb_cfg.trace(data,offset,max_span=length);calls=sorted(cfg["calls"],key=lambda x:x["source"]);expected_calls=1 if spec["mode"]=="bios-call" else 0
  if cfg["range_end"]!=ROM_BASE+offset+length or len(cfg["returns"])!=1 or len(calls)!=expected_calls:raise ValueError(f"CFG boundary mismatch: {rid}")
  map_path=Path(f"analysis/{rid}-wait-for-vblank-disassembly.json")
  evidence={"schema_version":1,"axis":"Disassembly","target":{"release":rid,"sha256":sha},"profile":profile,"origin_reference":index==0,"source":source_path.as_posix(),"source_sha256":source_sha,"function":{"name":"WaitForVBlank","address":f"0x{ROM_BASE+offset:08X}","range_end_exclusive":f"0x{ROM_BASE+offset+length:08X}","rom_code_range":{"start_offset":offset,"end_offset_exclusive":offset+length,"length":length,"sha256":digest(data[offset:offset+length]),"raw_bytes_published":False},"control_flow":{"instruction_halfwords":cfg["instruction_halfwords"],"edge_count":len(cfg["edges"]),"return_count":len(cfg["returns"]),"call_count":len(calls),"canonical_instruction_bytes_sha256":cfg["canonical_instruction_bytes_sha256"],"raw_halfwords_omitted":True}},"literal_addresses":{"gMain":f"0x{g_main:08X}","gMain_pointer":f"0x{ROM_BASE+g_lit:08X}","clear_mask":f"0x{ROM_BASE+mask_lit:08X}"},"state":{"intrCheck_offset":INTR_CHECK_OFFSET,"cleared_mask":1},"wait":{"mode":spec["mode"],"call":{"name":"VBlankIntrWait","target":f"0x{calls[0]['target']:08X}"} if calls else None},"naming_basis":{"repository":spec["repository"],"commit":spec["commit"],"path":"src/main.c","match_kind":"independent Thumb data access, CFG, literals and wait behavior"},"raw_rom_bytes_included":False}
  write_json(root/map_path,evidence);maps.append(map_path);records.append({"id":rid,"language":release["language"],"revision":release["revision"],"build_kind":release["build_kind"],"sha256":sha,"origin_reference":index==0,"address":evidence["function"]["address"],"code_sha256":evidence["function"]["rom_code_range"]["sha256"],"wait_mode":spec["mode"],"evidence":map_path.as_posix()})
 summary={"schema_version":1,"axis":"Disassembly","game":game,"function":"WaitForVBlank","profile":profile,"origin_reference":releases[0]["id"],"release_count":len(records),"source":source_path.as_posix(),"releases":records,"raw_rom_bytes_included":False};summary_path=Path("analysis/wait-for-vblank-disassembly-summary.json");write_json(root/summary_path,summary);languages=", ".join(dict.fromkeys(x["language"] for x in records));research=Path("research/wait-for-vblank-disassembly.md")
 (root/research).write_text(f"# {game} WaitForVBlank disassembly\n\n{releases[0]['id']} is the Japanese origin reference. All {len(records)} cataloged releases ({languages}) clear bit zero of gMain.intrCheck at offset 0x{INTR_CHECK_OFFSET:X} and use the {spec['mode']} profile. Evidence preserves boundaries, hashes, literals and raw-free CFG facts without ROM bytes or instruction dumps.\n",encoding="utf-8",newline="\n")
 test=Path("tests/test_wait_for_vblank_disassembly.py");outputs=[catalog_path,source_path,summary_path,*maps,research,test];missing=[p.as_posix() for p in outputs if not(root/p).is_file()]
 if missing:raise ValueError("missing output(s): "+", ".join(missing))
 write_json(root/"manifests/wait-for-vblank-disassembly.json",{"schema_version":1,"axis":"Disassembly","game":game,"profile":profile,"origin_reference":releases[0]["id"],"release_count":len(records),"generator":{"repository":"SakuraiTsubaki/Disassembly","tool":"tools/catalog_gba_wait_for_vblank.py","tool_sha256":file_hash(Path(__file__))},"outputs":[{"path":p.as_posix(),"sha256":file_hash(root/p)} for p in outputs],"raw_rom_bytes_included":False});return summary
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument("--root",type=Path,required=True);p.add_argument("--rom-dir",type=Path,required=True);p.add_argument("--catalog",type=Path,required=True);p.add_argument("--game",required=True);p.add_argument("--profile",choices=sorted(PROFILES),required=True);a=p.parse_args()
 try:build(a.root,a.rom_dir,a.catalog,a.game,a.profile)
 except(OSError,KeyError,ValueError,json.JSONDecodeError,struct.error)as e:p.error(str(e))
 return 0
if __name__=="__main__":raise SystemExit(main())
