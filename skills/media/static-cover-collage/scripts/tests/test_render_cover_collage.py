#!/usr/bin/env python3
import json,sys,tempfile,unittest
from pathlib import Path
from PIL import Image
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from render_cover_collage import *
def spec(overwrite=True):return {"schema_version":1,"output":"out/cover.jpg","width":1080,"height":1920,"layout":{"preset":"vertical_story_asymmetric"},"sources":[{"path":"img/h.jpg","focus_x":.5,"focus_y":.5,"role":"hero"},{"path":"img/l.jpg","focus_x":.5,"focus_y":.5,"role":"support_left"},{"path":"img/r.jpg","focus_x":.5,"focus_y":.5,"role":"support_right"}],"text":{"accent_headline":"ПЕКИН","primary":"ПУТЕШЕСТВИЕ","keywords":"ОТЕЛЬ · МЕТРО · ГОРОД"},"overwrite":overwrite}
def platform_spec(preset,width,height):
 x=spec();x["width"]=width;x["height"]=height;x["layout"]={"preset":preset};return x
class Tests(unittest.TestCase):
 def test_output_may_not_alias_collage_source_or_natural_background(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);(root/"img").mkdir();(root/"generated").mkdir()
   for n in ("h.jpg","l.jpg","r.jpg"):Image.new("RGB",(20,20),"red").save(root/"img"/n)
   x=spec(True);x["output"]="img/h.jpg"
   with self.assertRaisesRegex(SpecError,"aliases source"):render_collage(root,x)
   Image.new("RGB",(20,20),"blue").save(root/"generated/bg.png")
   natural={"schema_version":1,"mode":"natural_composite","background":"generated/bg.png","output":"generated/bg.png","width":420,"height":654,"platform_preset":"instagram_reels_cover","focus_x":.5,"focus_y":.5,"text_anchor_x":.3,"text":{},"overwrite":True}
   with self.assertRaisesRegex(SpecError,"aliases background"):render_natural_cover(root,natural)

 def test_paths(self):
  self.assertTrue(is_safe_relative_path("a/b.jpg"));self.assertFalse(is_safe_relative_path("../x"));self.assertFalse(is_safe_relative_path("/x"))
 def test_crop_deterministic(self):
  a=compute_cover_crop(2000,1000,500,500,.2,.5);b=compute_cover_crop(2000,1000,500,500,.2,.5);self.assertEqual(a,b);self.assertEqual(a.scale,.5)
 def test_preset(self):
  p=normalized_to_pixel_cells(PRESET_CELLS["vertical_story_asymmetric"],1080,1920); self.assertEqual(len(p),4)
  by={c.name:c for c in p}; self.assertEqual(by["hero"].y+by["hero"].h,by["support_left"].y); self.assertEqual(by["support_left"].y+by["support_left"].h,by["text_panel"].y); self.assertEqual(by["text_panel"].y+by["text_panel"].h,1920); self.assertEqual(by["support_left"].w+by["support_right"].w,1080)
 def test_crop_safe_center_preset(self):
  p=normalized_to_pixel_cells(PRESET_CELLS["vertical_crop_safe_center"],1080,1920); by={c.name:c for c in p}; self.assertEqual(by["text_panel"].y,round(1920*.38)); self.assertEqual(by["text_panel"].y+by["text_panel"].h,round(1920*.62)); self.assertLess(by["text_panel"].y,960); self.assertGreater(by["text_panel"].y+by["text_panel"].h,960); self.assertEqual(by["support_left"].y,by["text_panel"].y+by["text_panel"].h)
 def test_validation(self):
  validate_spec_structure(spec());x=spec();x["schema_version"]=2
  with self.assertRaises(SpecError):validate_spec_structure(x)
 def test_render_atomic_hash_overwrite(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);(root/"img").mkdir()
   for n,sz,c in [("h.jpg",(2000,1200),"red"),("l.jpg",(800,600),"blue"),("r.jpg",(800,600),"green")]:Image.new("RGB",sz,c).save(root/"img"/n)
   r=render_collage(root,spec(False));out=root/"out/cover.jpg";self.assertTrue(out.is_file());self.assertEqual(r["output"]["sha256"],sha256_file(out));
   with Image.open(out) as im:self.assertEqual(im.size,(1080,1920))
   self.assertEqual(list((root/"out").glob(".cover-collage-*")),[])
   with self.assertRaises(SpecError):render_collage(root,spec(False))
 def test_text_rows_have_separate_bands(self):
  c=PixelCell("text_panel",0,1421,1080,499,"text_panel"); self.assertLess(c.y+round(c.h*.19),c.y+round(c.h*.50)); self.assertLess(c.y+round(c.h*.50),c.y+round(c.h*.78)); self.assertGreater(round(c.h*(.50-.19)),100); self.assertGreater(round(c.h*(.78-.50)),100)
 def test_custom_outside_canvas(self):
  x=spec();x["layout"]={"cells":{"hero":{"x":.8,"y":0,"w":.3,"h":1,"type":"image"},"support_left":{"x":0,"y":0,"w":.3,"h":.5,"type":"image"},"support_right":{"x":.3,"y":0,"w":.5,"h":.5,"type":"image"},"text":{"x":0,"y":.5,"w":.8,"h":.5,"type":"text_panel"}}}
  with self.assertRaises(SpecError):resolve_layout_cells(x)
 def test_platform_contracts_have_current_dimensions_and_provenance(self):
  self.assertEqual((PLATFORM_CONTRACTS["youtube_api_thumbnail"]["width"],PLATFORM_CONTRACTS["youtube_api_thumbnail"]["height"]),(3840,2160))
  self.assertEqual(PLATFORM_CONTRACTS["youtube_api_thumbnail"]["surface"],"standard_api_thumbnail")
  self.assertEqual((PLATFORM_CONTRACTS["youtube_shorts_cover"]["width"],PLATFORM_CONTRACTS["youtube_shorts_cover"]["height"]),(2160,3840))
  self.assertEqual((PLATFORM_CONTRACTS["instagram_reels_cover"]["width"],PLATFORM_CONTRACTS["instagram_reels_cover"]["height"]),(420,654))
  self.assertEqual((PLATFORM_CONTRACTS["telegram_story_cover"]["width"],PLATFORM_CONTRACTS["telegram_story_cover"]["height"]),(1080,1920))
  self.assertTrue(PLATFORM_CONTRACTS["youtube_shorts_cover"]["separate_cover_upload"])
  self.assertTrue(PLATFORM_CONTRACTS["instagram_reels_cover"]["separate_cover_upload"])
  self.assertFalse(PLATFORM_CONTRACTS["telegram_story_cover"]["separate_cover_upload"])
  self.assertEqual(PLATFORM_CONTRACTS["telegram_story_cover"]["dimensions_provenance"],"delivery_default")
 def test_platform_preset_rejects_wrong_dimensions(self):
  x=platform_spec("youtube_api_thumbnail",2160,3840)
  with self.assertRaisesRegex(SpecError,"3840x2160"):validate_spec_structure(x)
  x=platform_spec("youtube_shorts_cover",1080,1920)
  with self.assertRaisesRegex(SpecError,"2160x3840"):validate_spec_structure(x)
 def test_platform_render_reports_text_inside_safe_zone(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);(root/"img").mkdir()
   for n,c in [("h.jpg","red"),("l.jpg","blue"),("r.jpg","green")]:Image.new("RGB",(800,1200),c).save(root/"img"/n)
   x=platform_spec("instagram_reels_cover",420,654);r=render_collage(root,x)
   self.assertEqual(r["platform_contract"]["platform"],"instagram")
   safe=r["platform_contract"]["text_safe_rect_pixels"]
   for box in r["text_bounding_boxes"]:
    self.assertGreaterEqual(box["x0"],safe["x"])
    self.assertGreaterEqual(box["y0"],safe["y"])
    self.assertLessEqual(box["x1"],safe["x"]+safe["width"])
    self.assertLessEqual(box["y1"],safe["y"]+safe["height"])
 def test_natural_composite_renders_generated_background_without_cards(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);(root/"generated").mkdir();Image.new("RGB",(900,1400),"#48624f").save(root/"generated/bg.png")
   x={"schema_version":1,"mode":"natural_composite","background":"generated/bg.png","output":"out/natural.jpg","width":420,"height":654,"platform_preset":"instagram_reels_cover","focus_x":.5,"focus_y":.5,"text_anchor_x":.30,"text":{"accent_headline":"ПЕКИН","primary":"ЗООПАРК","keywords":"ПАНДЫ · ТИГРЫ"},"overwrite":False,"provenance":{"ai_assisted":True}}
   r=render_cover(root,x)
   self.assertEqual(r["mode"],"natural_composite")
   self.assertEqual(r["platform_contract"]["platform"],"instagram")
   self.assertTrue(r["provenance"]["ai_assisted"])
   self.assertNotIn("pixel_cells",r)
   safe=r["platform_contract"]["text_safe_rect_pixels"]
   self.assertLess(sum((b["x0"]+b["x1"])/2 for b in r["text_bounding_boxes"])/len(r["text_bounding_boxes"]),safe["x"]+safe["width"]*.40)
   with Image.open(root/"out/natural.jpg") as im:self.assertEqual(im.size,(420,654))
 def test_natural_scrim_has_feathered_edges_not_card_border(self):
  safe={"x":21,"y":118,"width":378,"height":419};m=make_soft_scrim_mask((420,654),safe)
  cy=safe["y"]+safe["height"]//2;edge=m.getpixel((safe["x"],cy));center=m.getpixel((safe["x"]+safe["width"]//2,cy))
  self.assertGreater(edge,0);self.assertLess(edge,center);self.assertGreater(center,100);self.assertEqual(m.getpixel((0,0)),0)
if __name__=="__main__":unittest.main()
