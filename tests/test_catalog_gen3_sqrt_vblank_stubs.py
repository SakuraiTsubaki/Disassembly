import importlib.util,pathlib,unittest
T=pathlib.Path(__file__).parents[1]/"tools/catalog_gen3_sqrt_vblank_stubs.py";S=importlib.util.spec_from_file_location("catalog_gen3_sqrt_vblank_stubs",T);M=importlib.util.module_from_spec(S);S.loader.exec_module(M)
class TCase(unittest.TestCase):
 def test_suite(self):self.assertEqual(M.locate(b"abc"+M.SUITE_SIGNATURE),[3]);self.assertEqual(M.SUITE_LENGTH,10)
 def test_bios_numbers(self):self.assertEqual(M.SQRT_SIGNATURE[:2],bytes.fromhex("08df"));self.assertIn(bytes.fromhex("05df"),M.VBLANK_SIGNATURE)
 def test_layout_delta(self):self.assertEqual(M.RESET_TO_SUITE_DELTA,28)
if __name__=="__main__":unittest.main()
