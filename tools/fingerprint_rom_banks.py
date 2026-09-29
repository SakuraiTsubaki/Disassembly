#!/usr/bin/env python3
"""Fingerprint fixed-size ROM banks without retaining ROM bytes."""
from __future__ import annotations
import argparse,csv,hashlib,json,math
from collections import Counter
from pathlib import Path

def entropy(data:bytes)->float:
 if not data:return 0.0
 counts=Counter(data);n=len(data)
 return -sum((count/n)*math.log2(count/n) for count in counts.values())

def fingerprint_bytes(data:bytes,bank_size:int=0x4000)->dict:
 if bank_size<=0:raise ValueError("bank size must be positive")
 if not data or len(data)%bank_size:raise ValueError("ROM size must be a nonzero multiple of bank size")
 source_sha256=hashlib.sha256(data).hexdigest();banks=[]
 for index,start in enumerate(range(0,len(data),bank_size)):
  chunk=data[start:start+bank_size];uniform=len(set(chunk))==1;fill=chunk[0] if uniform else None
  classification="header-and-code" if index==0 else ("padding" if fill in (0x00,0xFF) else "unclassified")
  banks.append({"bank":index,"file_start":start,"file_end":start+bank_size-1,"cpu_start":0 if index==0 else 0x4000,"cpu_end":0x3FFF if index==0 else 0x7FFF,"size":bank_size,"sha256":hashlib.sha256(chunk).hexdigest(),"entropy":round(entropy(chunk),6),"unique_bytes":len(set(chunk)),"zero_bytes":chunk.count(0),"ff_bytes":chunk.count(0xFF),"classification":classification,"status":"fingerprinted","confidence":"high" if index==0 or classification=="padding" else "low"})
 return {"schema_version":1,"size":len(data),"sha256":source_sha256,"bank_size":bank_size,"bank_count":len(banks),"banks":banks}

def write_csv(path:Path,report:dict)->None:
 fields=["bank","file_start","file_end","cpu_start","cpu_end","classification","status","confidence","source_sha256","notes"]
 with path.open("w",encoding="utf-8",newline="") as stream:
  writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader()
  for b in report["banks"]:writer.writerow({"bank":f"0x{b['bank']:02x}","file_start":f"0x{b['file_start']:06x}","file_end":f"0x{b['file_end']:06x}","cpu_start":f"0x{b['cpu_start']:04x}","cpu_end":f"0x{b['cpu_end']:04x}","classification":b["classification"],"status":b["status"],"confidence":b["confidence"],"source_sha256":report["sha256"],"notes":f"bank_sha256={b['sha256']}; entropy={b['entropy']}; unique_bytes={b['unique_bytes']}; zero_bytes={b['zero_bytes']}; ff_bytes={b['ff_bytes']}"})

def main()->int:
 p=argparse.ArgumentParser(description=__doc__);p.add_argument("path",type=Path);p.add_argument("--bank-size",type=lambda x:int(x,0),default=0x4000);p.add_argument("--json-output",type=Path);p.add_argument("--csv-output",type=Path);p.add_argument("--compact",action="store_true");a=p.parse_args()
 try:r=fingerprint_bytes(a.path.read_bytes(),a.bank_size)
 except (OSError,ValueError) as e:p.error(str(e))
 text=json.dumps(r,ensure_ascii=True,indent=None if a.compact else 2)+"\n"
 if a.json_output:a.json_output.write_text(text,encoding="utf-8",newline="\n")
 else:print(text,end="")
 if a.csv_output:write_csv(a.csv_output,r)
 return 0
if __name__=="__main__":raise SystemExit(main())

