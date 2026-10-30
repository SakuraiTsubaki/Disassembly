import importlib.util,pathlib,unittest
T=pathlib.Path(__file__).parents[1]/"tools/catalog_gen3_reset_stubs.py";S=importlib.util.spec_from_file_location("catalog_gen3_reset_stubs",T);M=importlib.util.module_from_spec(S);S.loader.exec_module(M)
class TCase(unittest.TestCase):
 def test_unique_suite(self):
  data=b"x"*9+M.SUITE_SIGNATURE+b"y";self.assertEqual(M.locate(data),[9]);self.assertEqual(M.SUITE_LENGTH,28)
 def test_adjacency(self):self.assertEqual(M.SUITE_SIGNATURE[M.REGISTER_LENGTH:],M.SOFT_RESET_SIGNATURE)
 def test_profiles_pinned(self):self.assertTrue(all(len(x["commit"])==40 for x in M.PROFILES.values()))
if __name__=="__main__":unittest.main()

