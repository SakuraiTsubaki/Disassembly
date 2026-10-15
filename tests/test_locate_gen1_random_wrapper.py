import importlib.util,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];S=importlib.util.spec_from_file_location('m',ROOT/'tools/locate_gen1_random_wrapper.py');M=importlib.util.module_from_spec(S);S.loader.exec_module(M)
def wrapper(bank=4,address=0x7fea,bankswitch=0x35d6,hadd=0xffd3):return bytes((0xe5,0xd5,0xc5,0x06,bank,0x21,address&255,address>>8,0xcd,bankswitch&255,bankswitch>>8,0xf0,hadd&255,0xc1,0xd1,0xe1,0xc9))
class Tests(unittest.TestCase):
 def test_extracts_dependencies(self):
  d=bytearray(0x9000);d[0x123:0x123+M.LENGTH]=wrapper();f=M.locate(bytes(d),4,0x7fea,0xffd3)[0];self.assertEqual(f['dependencies']['Bankswitch']['address'],0x35d6);self.assertEqual(f['preserved_registers'],['BC','DE','HL'])
 def test_rejects_wrong_target(self):self.assertEqual(M.locate(wrapper(),4,0x7feb,0xffd3),[])
 def test_rejects_wrong_hram(self):self.assertEqual(M.locate(wrapper(),4,0x7fea,0xffd2),[])
 def test_rejects_non_home_wrapper(self):
  d=bytearray(0x9000);d[0x8000:0x8000+M.LENGTH]=wrapper();self.assertEqual(M.locate(bytes(d),4,0x7fea,0xffd3),[])
if __name__=='__main__':unittest.main()
