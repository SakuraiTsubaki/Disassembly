import importlib.util,pathlib,unittest
TOOL=pathlib.Path(__file__).parents[1]/"tools"/"catalog_gba_wait_for_vblank.py";SPEC=importlib.util.spec_from_file_location("catalog_gba_wait_for_vblank",TOOL);M=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(M)
class Tests(unittest.TestCase):
 def test_profiles(self):self.assertEqual({k:(v["mode"],v["length"])for k,v in M.PROFILES.items()},{"rs":("bios-call",22),"emerald":("volatile-poll",40),"frlg":("volatile-poll",40)})
 def test_sources(self):self.assertIn("bl VBlankIntrWait",M.source_text("rs"));self.assertIn(".LWaitSet:",M.source_text("emerald"));self.assertNotIn(".hword",M.source_text("frlg"))
if __name__=="__main__":unittest.main()
