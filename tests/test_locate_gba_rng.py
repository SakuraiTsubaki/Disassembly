import importlib.util,struct,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location('locate_gba_rng',ROOT/'tools/locate_gba_rng.py');M=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(M)
class Tests(unittest.TestCase):
 def test_standard(self):
  d=bytearray(128);d[0:18]=M.packed(M.RANDOM['standard']);struct.pack_into('<III',d,20,0x03001234,M.MULTIPLIER,M.INCREMENT);d[32:42]=M.packed(M.SEED['standard']);struct.pack_into('<I',d,44,0x03001234);r=M.locate(bytes(d),'standard')[0];self.assertEqual(r['globals'],{'gRngValue':'0x03001234'});self.assertEqual(r['functions']['SeedRng']['rom_offset'],32)
 def test_emerald(self):
  d=bytearray(160);d[0:26]=M.packed(M.RANDOM['emerald']);struct.pack_into('<IIII',d,28,0x03005678,M.MULTIPLIER,M.INCREMENT,0x02001234);d[44:60]=M.packed(M.SEED['emerald']);struct.pack_into('<II',d,60,0x03005678,0x02001230);r=M.locate(bytes(d),'emerald')[0];self.assertEqual(r['globals']['sRandCount'],'0x02001234');self.assertEqual(r['globals']['sUnknown'],'0x02001230')
 def test_wrong_constant_rejected(self):
  d=bytearray(96);d[0:18]=M.packed(M.RANDOM['standard']);struct.pack_into('<III',d,20,0x03001234,1,M.INCREMENT);d[32:42]=M.packed(M.SEED['standard']);struct.pack_into('<I',d,44,0x03001234);self.assertEqual(M.locate(bytes(d),'standard'),[])
if __name__=='__main__':unittest.main()
