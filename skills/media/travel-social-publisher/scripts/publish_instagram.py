#!/usr/bin/env python3
"""Publish a Reel whose MP4 is already reachable at a public HTTPS URL."""
from __future__ import annotations
import argparse,json,os,time,urllib.parse,urllib.request

def post(url, fields):
    data=urllib.parse.urlencode(fields).encode(); return json.load(urllib.request.urlopen(urllib.request.Request(url,data=data,method='POST'),timeout=60))
def get(url, fields):
    return json.load(urllib.request.urlopen(url+'?'+urllib.parse.urlencode(fields),timeout=60))
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--video-url',required=True); ap.add_argument('--caption-file',required=True); ap.add_argument('--share-to-feed',action='store_true'); a=ap.parse_args()
    if not a.video_url.startswith('https://'): raise SystemExit('video-url must be public HTTPS')
    token=os.environ.get('INSTAGRAM_ACCESS_TOKEN'); user=os.environ.get('INSTAGRAM_USER_ID'); version=os.environ.get('INSTAGRAM_API_VERSION','v24.0')
    if not token or not user: raise SystemExit('missing INSTAGRAM_ACCESS_TOKEN or INSTAGRAM_USER_ID')
    base=f'https://graph.instagram.com/{version}'
    c=post(f'{base}/{user}/media',{'media_type':'REELS','video_url':a.video_url,'caption':open(a.caption_file,encoding='utf-8').read().strip(),'share_to_feed':str(a.share_to_feed).lower(),'access_token':token})['id']
    for _ in range(60):
        s=get(f'{base}/{c}',{'fields':'status_code,status','access_token':token})
        if s.get('status_code')=='FINISHED': break
        if s.get('status_code') in {'ERROR','EXPIRED'}: raise SystemExit('container failed: '+json.dumps({k:v for k,v in s.items() if k!='access_token'}))
        time.sleep(5)
    else: raise SystemExit('container not ready after 5 minutes')
    p=post(f'{base}/{user}/media_publish',{'creation_id':c,'access_token':token})
    print(json.dumps({'platform':'instagram','id':p['id'],'container_id':c},ensure_ascii=False))
if __name__=='__main__': main()
