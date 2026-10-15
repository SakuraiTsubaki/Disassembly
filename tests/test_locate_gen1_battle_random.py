import importlib.util,unittest
from pathlib import Path
R=Path(__file__).resolve().parents[1];S=importlib.util.spec_from_file_location('m',R/'tools/locate_gen1_battle_random.py');M=importlib.util.module_from_spec(S);S.loader.exec_module(M)
def routine(random=0x3e8c,link=0xd057,state=2,index=0xccd3,seeds=0xcce2):return bytes((0xfa,link&255,link>>8,0xfe,state,0xc2,random&255,random>>8,0xe5,0xc5,0xfa,index&255,index>>8,0x4f,0x06,0,0x21,seeds&255,seeds>>8,0x09,0x3c,0xea,index&255,index>>8,0xfe,9,0x7e,0xc1,0xe1,0xd8,0xe5,0xc5,0xf5,0xaf,0xea,index&255,index>>8,0x21,seeds&255,seeds>>8,0x06,9,0x7e,0x4f,0x87,0x87,0x81,0x3c,0x22,0x05,0x20,0xf6,0xf1,0xc1,0xe1,0xc9))
class Tests(unittest.TestCase):
 def test_extracts_state(self):
  f=M.candidate(routine(),0,0x3e8c);self.assertEqual(f['state']['refreshed_seed_count'],9);self.assertEqual(f['state']['stream_length'],10);self.assertEqual(f['control_flow']['non_link_jump']['address'],0x3e8c)
 def test_rejects_wrong_random(self):self.assertIsNone(M.candidate(routine(),0,0x3e8d))
 def test_rejects_mismatched_index(self):
  b=bytearray(routine());b[35]^=1;self.assertIsNone(M.candidate(bytes(b),0,0x3e8c))
 def test_rejects_broken_loop(self):
  b=bytearray(routine());b[51]=0xf5;self.assertIsNone(M.candidate(bytes(b),0,0x3e8c))
if __name__=='__main__':unittest.main()
