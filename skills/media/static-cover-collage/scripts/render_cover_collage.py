#!/usr/bin/env python3
"""Render static cover collages from a JSON spec (stdlib + Pillow)."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from PIL import Image, ImageDraw, ImageFilter, ImageFont
except ImportError as exc:
    raise SystemExit("Pillow is required. Install it in a venv with: uv pip install Pillow") from exc

SCHEMA_VERSION = 1
JPEG_QUALITY = 92
PRESET_CELLS = {
    "youtube_api_thumbnail": {
        "hero": {"x": 0.0, "y": 0.0, "w": 0.55, "h": 1.0, "type": "image"},
        "support_left": {"x": 0.55, "y": 0.0, "w": 0.45, "h": 0.5, "type": "image"},
        "support_right": {"x": 0.55, "y": 0.5, "w": 0.45, "h": 0.5, "type": "image"},
        "text_panel": {"x": 0.06, "y": 0.55, "w": 0.43, "h": 0.34, "type": "text_panel"},
    },
    "vertical_story_asymmetric": {
        "hero": {"x": 0.0, "y": 0.0, "w": 1.0, "h": 0.52, "type": "image"},
        "support_left": {"x": 0.0, "y": 0.52, "w": 0.5, "h": 0.22, "type": "image"},
        "support_right": {"x": 0.5, "y": 0.52, "w": 0.5, "h": 0.22, "type": "image"},
        "text_panel": {"x": 0.0, "y": 0.74, "w": 1.0, "h": 0.26, "type": "text_panel"},
    },
    "vertical_crop_safe_center": {
        "hero": {"x": 0.0, "y": 0.0, "w": 1.0, "h": 0.38, "type": "image"},
        "text_panel": {"x": 0.0, "y": 0.38, "w": 1.0, "h": 0.24, "type": "text_panel"},
        "support_left": {"x": 0.0, "y": 0.62, "w": 0.5, "h": 0.38, "type": "image"},
        "support_right": {"x": 0.5, "y": 0.62, "w": 0.5, "h": 0.38, "type": "image"},
    },
    "youtube_shorts_cover": {
        "hero": {"x": 0.0, "y": 0.0, "w": 1.0, "h": 0.38, "type": "image"},
        "support_left": {"x": 0.0, "y": 0.38, "w": 0.5, "h": 0.62, "type": "image"},
        "support_right": {"x": 0.5, "y": 0.38, "w": 0.5, "h": 0.62, "type": "image"},
        "text_panel": {"x": 0.08, "y": 0.38, "w": 0.72, "h": 0.24, "type": "text_panel"},
    },
    "instagram_reels_cover": {
        "hero": {"x": 0.0, "y": 0.0, "w": 1.0, "h": 0.38, "type": "image"},
        "support_left": {"x": 0.0, "y": 0.38, "w": 0.5, "h": 0.62, "type": "image"},
        "support_right": {"x": 0.5, "y": 0.38, "w": 0.5, "h": 0.62, "type": "image"},
        "text_panel": {"x": 0.05, "y": 0.38, "w": 0.90, "h": 0.24, "type": "text_panel"},
    },
    "telegram_story_cover": {
        "hero": {"x": 0.0, "y": 0.0, "w": 1.0, "h": 0.38, "type": "image"},
        "support_left": {"x": 0.0, "y": 0.38, "w": 0.5, "h": 0.62, "type": "image"},
        "support_right": {"x": 0.5, "y": 0.38, "w": 0.5, "h": 0.62, "type": "image"},
        "text_panel": {"x": 0.05, "y": 0.38, "w": 0.90, "h": 0.24, "type": "text_panel"},
    },
}
PLATFORM_CONTRACTS = {
    "youtube_api_thumbnail": {
        "platform":"youtube", "surface":"standard_api_thumbnail", "width":3840, "height":2160,
        "dimensions_provenance":"official", "separate_cover_upload":True,
        "official_source":"https://support.google.com/youtube/answer/72431?hl=en",
        "text_safe_rect":[0.05,0.05,0.90,0.90], "safe_zone_provenance":"conservative_margin_policy",
    },
    "youtube_shorts_cover": {
        "platform":"youtube", "surface":"shorts_custom_thumbnail", "width":2160, "height":3840,
        "dimensions_provenance":"official", "separate_cover_upload":True,
        "official_source":"https://support.google.com/youtube/answer/72431?hl=en",
        "text_safe_rect":[0.08,0.29,0.72,0.42],
        "safe_zone_provenance":"local_youtube_shorts_ui_and_telegram_og_center_crop_policy",
    },
    "instagram_reels_cover": {
        "platform":"instagram", "surface":"reels_cover_photo", "width":420, "height":654,
        "dimensions_provenance":"official", "separate_cover_upload":True,
        "official_source":"https://www.facebook.com/help/instagram/1038071743007909",
        "text_safe_rect":[0.05,0.18,0.90,0.64], "safe_zone_provenance":"conservative_crop_policy",
    },
    "telegram_story_cover": {
        "platform":"telegram", "surface":"story_first_frame", "width":1080, "height":1920,
        "dimensions_provenance":"delivery_default", "separate_cover_upload":False,
        "official_source":"https://core.telegram.org/method/stories.sendStory",
        "text_safe_rect":[0.05,0.12,0.90,0.68], "safe_zone_provenance":"conservative_ui_policy",
    },
}
DEFAULT_COLORS = {"text_panel":"#141414","accent":"#FFD700","primary":"#FFFFFF","keywords":"#FFFFFF","stroke":"#000000"}
FONT_ROOTS=[Path("/usr/share/fonts"),Path("/usr/local/share/fonts"),Path.home()/".fonts",Path.home()/".local/share/fonts"]
FONT_RE=re.compile(r"DejaVuSans-Bold\.(ttf|otf)$",re.I)
PATH_RE=re.compile(r"^(?!/)(?!.*\.\.)[^\0]+$")
class SpecError(ValueError): pass
@dataclass(frozen=True)
class PixelCell: name:str; x:int; y:int; w:int; h:int; cell_type:str
@dataclass(frozen=True)
class CropGeometry: scale:float; crop_box:Tuple[int,int,int,int]; source_size:Tuple[int,int]; target_size:Tuple[int,int]
def is_safe_relative_path(p): return bool(p and not p.startswith("/") and "\\" not in p and ".." not in p.split("/") and PATH_RE.match(p))
def resolve_under_root(root,p):
    if not is_safe_relative_path(p): raise SpecError(f"Unsafe path rejected: {p}")
    q=(root/p).resolve()
    try:q.relative_to(root.resolve())
    except ValueError: raise SpecError(f"Path traversal rejected: {p}") from None
    return q
def sha256_file(p):
    h=hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda:f.read(65536),b""):h.update(b)
    return h.hexdigest()
def validate_spec_structure(s):
    if s.get("schema_version")!=1: raise SpecError("schema_version must be 1")
    if not isinstance(s.get("output"),str) or not is_safe_relative_path(s["output"]): raise SpecError("output must be safe relative path")
    if not all(isinstance(s.get(k),int) and 1<=s[k]<=8192 for k in ("width","height")): raise SpecError("width/height out of range")
    l=s.get("layout");
    if not isinstance(l,dict) or (("preset" in l)==("cells" in l)): raise SpecError("layout requires exactly one of preset/cells")
    if "preset" in l and l["preset"] not in PRESET_CELLS: raise SpecError("unknown preset")
    if "preset" in l and l["preset"] in PLATFORM_CONTRACTS:
        c=PLATFORM_CONTRACTS[l["preset"]]
        if (s["width"],s["height"]) != (c["width"],c["height"]): raise SpecError(f"{l['preset']} requires {c['width']}x{c['height']}")
    src=s.get("sources")
    if not isinstance(src,list) or not 2<=len(src)<=6: raise SpecError("sources must contain 2-6 items")
    roles=set()
    for x in src:
        if not isinstance(x.get("path"),str) or not is_safe_relative_path(x["path"]): raise SpecError("unsafe source path")
        if any(not isinstance(x.get(k),(int,float)) or not 0<=x[k]<=1 for k in ("focus_x","focus_y")): raise SpecError("focus must be 0-1")
        if not x.get("role") or x["role"] in roles: raise SpecError("invalid/duplicate role")
        roles.add(x["role"])
    if not isinstance(s.get("text"),dict) or not isinstance(s.get("overwrite"),bool): raise SpecError("text/overwrite invalid")
def resolve_layout_cells(s):
    if "preset" in s["layout"]: return {k:dict(v) for k,v in PRESET_CELLS[s["layout"]["preset"]].items()}
    out={}
    for n,c in s["layout"]["cells"].items():
        if c.get("type") not in ("image","text_panel") or any(k not in c for k in ("x","y","w","h")): raise SpecError("invalid cell")
        if c["x"]<0 or c["y"]<0 or c["w"]<=0 or c["h"]<=0 or c["x"]+c["w"]>1.00001 or c["y"]+c["h"]>1.00001: raise SpecError("cell outside canvas")
        out[n]=dict(c)
    return out
def validate_roles_against_cells(cells,sources):
    images={n for n,c in cells.items() if c["type"]=="image"}; panels=[n for n,c in cells.items() if c["type"]=="text_panel"]
    if len(panels)!=1 or images!={s["role"] for s in sources}: raise SpecError("roles must match image cells and one text_panel")
def normalized_to_pixel_cells(cells,w,h):
    out=[]
    for n,c in cells.items():
        x0=round(c["x"]*w); y0=round(c["y"]*h); x1=round((c["x"]+c["w"])*w); y1=round((c["y"]+c["h"])*h)
        out.append(PixelCell(n,x0,y0,max(1,min(x1,w)-x0),max(1,min(y1,h)-y0),c["type"]))
    return out
def compute_cover_crop(sw,sh,tw,th,fx,fy):
    scale=max(tw/sw,th/sh); rw,rh=sw*scale,sh*scale; left=max(0,min(fx*rw-tw/2,rw-tw)); top=max(0,min(fy*rh-th/2,rh-th))
    return CropGeometry(scale,(round(left),round(top),round(left+tw),round(top+th)),(sw,sh),(tw,th))
def cover_crop_image(im,tw,th,fx,fy):
    g=compute_cover_crop(im.width,im.height,tw,th,fx,fy); r=im.resize((round(im.width*g.scale),round(im.height*g.scale)),Image.Resampling.LANCZOS); return r.crop(g.crop_box)
def discover_dejavu_bold():
    found=[]
    for root in FONT_ROOTS:
        if root.is_dir():
            for dp,_,fs in os.walk(root): found += [Path(dp)/f for f in fs if FONT_RE.search(f)]
    if not found: raise SpecError("DejaVu Sans Bold not found")
    return sorted(found)[0]
def rgb(x): return tuple(int(x[i:i+2],16) for i in (1,3,5))
def fit_font(draw,text,path,maxw,start,minsize=12):
    for z in range(start,minsize-1,-2):
        f=ImageFont.truetype(str(path),z); b=draw.textbbox((0,0),text,font=f)
        if b[2]-b[0]<=maxw:return f
    return ImageFont.truetype(str(path),minsize)
def render_text_panel(canvas,c,text,colors,fontpath):
    d=ImageDraw.Draw(canvas); d.rectangle((c.x,c.y,c.x+c.w,c.y+c.h),fill=rgb(colors["text_panel"])); maxw=round(c.w*.88); cx=c.x+c.w//2; stroke=max(2,round(canvas.height*.003))
    specs=[((text.get("accent_headline")or"").strip(),.19,.23,colors["accent"],True),((text.get("primary")or"").strip(),.50,.16,colors["primary"],True),((text.get("keywords")or"").strip(),.78,.105,colors["keywords"],False)]
    boxes=[]
    for t,yfrac,sizefrac,col,st in specs:
        if not t: continue
        sw=stroke if st else 0; cy=c.y+round(c.h*yfrac); f=fit_font(d,t,fontpath,maxw,round(c.h*sizefrac)); d.text((cx,cy),t,font=f,fill=rgb(col),anchor="mm",stroke_width=sw,stroke_fill=rgb(colors["stroke"])); b=d.textbbox((cx,cy),t,font=f,anchor="mm",stroke_width=sw); boxes.append({"text":t,"x0":b[0],"y0":b[1],"x1":b[2],"y1":b[3]})
    return boxes
def atomic_image(im,p):
    p.parent.mkdir(parents=True,exist_ok=True); fd,n=tempfile.mkstemp(prefix=".cover-collage-",suffix=".jpg",dir=p.parent); os.close(fd); q=Path(n)
    try: im.save(q,"JPEG",quality=92,optimize=True); os.replace(q,p)
    finally:
        if q.exists():q.unlink()
def atomic_json(x,p):
    p.parent.mkdir(parents=True,exist_ok=True); fd,n=tempfile.mkstemp(prefix=".cover-collage-",suffix=".json",dir=p.parent); os.close(fd); q=Path(n)
    try:q.write_text(json.dumps(x,ensure_ascii=False,indent=2)+"\n",encoding="utf-8");os.replace(q,p)
    finally:
        if q.exists():q.unlink()
def report_path_for(p):return p.with_suffix(p.suffix+".report.json")
def render_collage(root,s):
    validate_spec_structure(s); cells=resolve_layout_cells(s);validate_roles_against_cells(cells,s["sources"]); px=normalized_to_pixel_cells(cells,s["width"],s["height"]); font=discover_dejavu_bold(); out=resolve_under_root(root,s["output"]); rep=report_path_for(out)
    source_paths=[resolve_under_root(root,x["path"]) for x in s["sources"]]
    if out in source_paths:raise SpecError("output aliases source")
    if rep.resolve(strict=False) in source_paths or any(rep.exists() and os.path.samefile(rep,p) for p in source_paths):raise SpecError("report aliases source")
    if not s["overwrite"] and (out.exists() or rep.exists()):raise SpecError("output/report exists")
    colors=dict(DEFAULT_COLORS);colors.update(s.get("colors",{})); role={x["role"]:x for x in s["sources"]}; hashes={};geoms={};text_boxes=[];canvas=Image.new("RGB",(s["width"],s["height"]),(0,0,0))
    for c in px:
        if c.cell_type=="image":
            x=role[c.name];p=resolve_under_root(root,x["path"])
            if not p.is_file():raise SpecError(f"Source not found: {x['path']}")
            hashes[x["path"]]=sha256_file(p)
            with Image.open(p) as im:
                im=im.convert("RGB");g=compute_cover_crop(im.width,im.height,c.w,c.h,x["focus_x"],x["focus_y"]);geoms[c.name]={"scale":g.scale,"crop_box":list(g.crop_box),"source_size":list(g.source_size),"target_size":list(g.target_size)};canvas.paste(cover_crop_image(im,c.w,c.h,x["focus_x"],x["focus_y"]),(c.x,c.y))
        else:text_boxes.extend(render_text_panel(canvas,c,s["text"],colors,font))
    contract=None
    preset=s["layout"].get("preset")
    if preset in PLATFORM_CONTRACTS:
        contract=dict(PLATFORM_CONTRACTS[preset]); x,y,w,h=contract.pop("text_safe_rect"); safe={"x":round(x*s["width"]),"y":round(y*s["height"]),"width":round(w*s["width"]),"height":round(h*s["height"])}; contract["text_safe_rect_pixels"]=safe
        if any(b["x0"]<safe["x"] or b["y0"]<safe["y"] or b["x1"]>safe["x"]+safe["width"] or b["y1"]>safe["y"]+safe["height"] for b in text_boxes): raise SpecError("rendered text outside platform safe zone")
    atomic_image(canvas,out); report={"schema_version":1,"source_sha256":hashes,"normalized_spec":{**s,"layout":{**s["layout"],"cells":cells}},"pixel_cells":[vars(c) for c in px],"crop_geometries":geoms,"fonts":{"bold":str(font)},"text_bounding_boxes":text_boxes,"platform_contract":contract,"output":{"path":s["output"],"sha256":sha256_file(out),"width":s["width"],"height":s["height"],"format":"JPEG"},"visual_review":"pending"};atomic_json(report,rep);return report
def platform_contract_for(preset,w,h):
    if preset not in PLATFORM_CONTRACTS: raise SpecError("unknown platform_preset")
    base=PLATFORM_CONTRACTS[preset]
    if (w,h)!=(base["width"],base["height"]): raise SpecError(f"{preset} requires {base['width']}x{base['height']}")
    c=dict(base);x,y,sw,sh=c.pop("text_safe_rect");c["text_safe_rect_pixels"]={"x":round(x*w),"y":round(y*h),"width":round(sw*w),"height":round(sh*h)};return c
def validate_natural_spec(s):
    if s.get("schema_version")!=1 or s.get("mode")!="natural_composite": raise SpecError("natural_composite schema invalid")
    for k in ("background","output"):
        if not isinstance(s.get(k),str) or not is_safe_relative_path(s[k]): raise SpecError(f"unsafe {k}")
    if not all(isinstance(s.get(k),int) and 1<=s[k]<=8192 for k in ("width","height")): raise SpecError("width/height out of range")
    platform_contract_for(s.get("platform_preset"),s["width"],s["height"])
    if any(not isinstance(s.get(k),(int,float)) or not 0<=s[k]<=1 for k in ("focus_x","focus_y")): raise SpecError("focus must be 0-1")
    if not isinstance(s.get("text_anchor_x",.5),(int,float)) or not .15<=s.get("text_anchor_x",.5)<=.85: raise SpecError("text_anchor_x must be 0.15-0.85")
    if not isinstance(s.get("text"),dict) or not isinstance(s.get("overwrite"),bool): raise SpecError("text/overwrite invalid")
def make_soft_scrim_mask(size,safe):
    mask=Image.new("L",size,0);m=ImageDraw.Draw(mask);x0=safe["x"];x1=safe["x"]+safe["width"];y0=safe["y"]+round(safe["height"]*.18);y1=safe["y"]+round(safe["height"]*.66);m.rectangle((x0,y0,x1,y1),fill=142);return mask.filter(ImageFilter.GaussianBlur(radius=max(8,round(size[1]*.04))))
def apply_soft_scrim(canvas,safe):
    mask=make_soft_scrim_mask(canvas.size,safe);canvas.paste(Image.new("RGB",canvas.size,(8,12,10)),(0,0),mask)
def render_natural_text(canvas,text,colors,fontpath,safe,anchor_x=.5):
    d=ImageDraw.Draw(canvas);cx=safe["x"]+round(safe["width"]*anchor_x);maxw=round(min(cx-safe["x"],safe["x"]+safe["width"]-cx)*2*.90);stroke=max(2,round(canvas.height*.003));specs=[((text.get("accent_headline")or"").strip(),.30,.105,colors["accent"]),((text.get("primary")or"").strip(),.43,.075,colors["primary"]),((text.get("keywords")or"").strip(),.56,.042,colors["keywords"])]
    boxes=[]
    for t,yf,sf,col in specs:
        if not t:continue
        cy=safe["y"]+round(safe["height"]*yf);f=fit_font(d,t,fontpath,maxw,round(canvas.height*sf));d.text((cx,cy),t,font=f,fill=rgb(col),anchor="mm",stroke_width=stroke,stroke_fill=rgb(colors["stroke"]));b=d.textbbox((cx,cy),t,font=f,anchor="mm",stroke_width=stroke);boxes.append({"text":t,"x0":b[0],"y0":b[1],"x1":b[2],"y1":b[3]})
    return boxes
def render_natural_cover(root,s):
    validate_natural_spec(s);out=resolve_under_root(root,s["output"]);rep=report_path_for(out);bg=resolve_under_root(root,s["background"])
    if out==bg:raise SpecError("output aliases background")
    if rep.resolve(strict=False)==bg or (rep.exists() and os.path.samefile(rep,bg)):raise SpecError("report aliases background")
    if not bg.is_file():raise SpecError("background not found")
    if not s["overwrite"] and (out.exists() or rep.exists()):raise SpecError("output/report exists")
    with Image.open(bg) as im:canvas=cover_crop_image(im.convert("RGB"),s["width"],s["height"],s["focus_x"],s["focus_y"])
    contract=platform_contract_for(s["platform_preset"],s["width"],s["height"]);safe=contract["text_safe_rect_pixels"];apply_soft_scrim(canvas,safe);colors=dict(DEFAULT_COLORS);colors.update(s.get("colors",{}));font=discover_dejavu_bold();boxes=render_natural_text(canvas,s["text"],colors,font,safe,s.get("text_anchor_x",.5))
    if any(b["x0"]<safe["x"] or b["y0"]<safe["y"] or b["x1"]>safe["x"]+safe["width"] or b["y1"]>safe["y"]+safe["height"] for b in boxes):raise SpecError("rendered text outside platform safe zone")
    atomic_image(canvas,out);report={"schema_version":1,"mode":"natural_composite","background_sha256":sha256_file(bg),"provenance":dict(s.get("provenance",{})),"normalized_spec":s,"fonts":{"bold":str(font)},"text_bounding_boxes":boxes,"platform_contract":contract,"output":{"path":s["output"],"sha256":sha256_file(out),"width":s["width"],"height":s["height"],"format":"JPEG"},"visual_review":"pending","identity_review":"pending"};atomic_json(report,rep);return report
def render_cover(root,s):
    return render_natural_cover(root,s) if s.get("mode")=="natural_composite" else render_collage(root,s)
def main():
    a=argparse.ArgumentParser();a.add_argument("--root",required=True,type=Path);a.add_argument("--spec",required=True,type=Path);x=a.parse_args();root=x.root.resolve();sp=x.spec if x.spec.is_absolute() else root/x.spec
    try:r=render_cover(root,json.loads(sp.read_text(encoding="utf-8")));print(json.dumps({"status":"ok","output":r["output"]},ensure_ascii=False));return 0
    except (SpecError,OSError,ValueError) as e:print(f"error: {e}",file=sys.stderr);return 2
if __name__=="__main__":raise SystemExit(main())
