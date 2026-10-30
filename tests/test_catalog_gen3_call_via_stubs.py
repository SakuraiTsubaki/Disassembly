import importlib.util,pathlib,unittest
T=pathlib.Path(__file__).parents[1]/"tools/catalog_gen3_call_via_stubs.py";S=importlib.util.spec_from_file_location("catalog_gen3_call_via_stubs",T);M=importlib.util.module_from_spec(S);S.loader.exec_module(M)
class TCase(unittest.TestCase):
 def test_suite(self):self.assertEqual(len(M.FUNCTIONS),15);self.assertEqual(M.SUITE_LENGTH,60);self.assertEqual(M.locate(b"x"+M.SUITE_SIGNATURE),[1])
 def test_encodings(self):self.assertEqual(M.encoding(0),bytes.fromhex("0047c046"));self.assertEqual(M.encoding(14),bytes.fromhex("7047c046"))
 def test_names(self):self.assertEqual([x[0]for x in M.FUNCTIONS[-5:]],["_call_via_sl","_call_via_fp","_call_via_ip","_call_via_sp","_call_via_lr"])
 def test_anchor_delta(self):self.assertEqual(M.VBLANK_END_TO_SUITE_DELTA,2);self.assertEqual(M.ALIGNMENT_PADDING,b"\0\0")
if __name__=="__main__":unittest.main()
