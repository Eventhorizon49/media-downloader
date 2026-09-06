import base64,hashlib,hmac,json,os,re,shutil,tempfile,time,zipfile
from pathlib import Path
from urllib.parse import urlparse
import imageio_ffmpeg,yt_dlp
from curl_cffi import requests as cr
from fastapi import BackgroundTasks,FastAPI,HTTPException,Query
from fastapi.responses import FileResponse,HTMLResponse
from pydantic import BaseModel

app=FastAPI(title='Media Downloader',version='1.4.1')
SECRET=os.getenv('TOKEN_SECRET','dev-change-me');FFMPEG=imageio_ffmpeg.get_ffmpeg_exe();ROOT=Path(__file__).resolve().parent
SUPPORTED=('instagram.com','x.com','twitter.com','reddit.com','redd.it');UA='MediaDownloader/1.4 (+https://media-downloader-pcbv.onrender.com) Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 Chrome/131.0 Mobile Safari/537.36';IMAGE_EXTS=('.jpg','.jpeg','.png','.webp','.gif');DIRECT_EXTS=IMAGE_EXTS+('.mp4','.mov','.webm','.m4a','.aac')
class AnalyzeRequest(BaseModel): url:str
class BatchRequest(BaseModel): tokens:list[str]
def host(u):return (urlparse(u).hostname or '').lower()
def platform(u):
 h=host(u);return 'Instagram' if 'instagram' in h else ('Reddit' if 'reddit' in h or 'redd.it' in h else 'X / Twitter')
def valid(u):
 try:
  p=urlparse(u);return p.scheme in ('http','https') and any(host(u)==d or host(u).endswith('.'+d) for d in SUPPORTED)
 except:return False
def sign(p):
 raw=base64.urlsafe_b64encode(json.dumps(p,separators=(',',':')).encode()).decode().rstrip('=');return raw+'.'+hmac.new(SECRET.encode(),raw.encode(),hashlib.sha256).hexdigest()
def unsign(t):
 try:
  raw,s=t.rsplit('.',1);assert hmac.compare_digest(s,hmac.new(SECRET.encode(),raw.encode(),hashlib.sha256).hexdigest());p=json.loads(base64.urlsafe_b64decode(raw+'='*(-len(raw)%4)));assert p.get('exp',0)>=time.time();return p
 except:raise HTTPException(410,'Download session expired. Analyze the link again.')
def cookie_file():
 v=os.getenv('YTDLP_COOKIES_B64')
 if not v:return None
 try:
  f=tempfile.NamedTemporaryFile(delete=False,suffix='.txt');f.write(base64.b64decode(v));f.close();return f.name
 except:return None
def opts(download=False,out=None,fmt=None):
 o={'quiet':True,'no_warnings':True,'noplaylist':False,'ffmpeg_location':FFMPEG,'socket_timeout':30,'retries':3,'fragment_retries':3,'concurrent_fragment_downloads':4,'http_headers':{'User-Agent':UA}};c=cookie_file()
 if c:o['cookiefile']=c
 if download:o.update({'outtmpl':out,'format':fmt or 'bestvideo*+bestaudio/best','merge_output_format':'mp4','restrictfilenames':True,'noplaylist':True})
 else:o['skip_download']=True
 return o,c
def ytdlp(u):
 o,c=opts()
 try:
  with yt_dlp.YoutubeDL(o) as y:return y.extract_info(u,download=False)
 finally:
  if c:
   try:os.remove(c)
   except:pass
def flat(info):
 e=[x for x in (info.get('entries') or []) if x]
 if not e:return [info]
 out=[]
 for x in e:out.extend([z for z in (x.get('entries') or []) if z] or [x])
 return out or [info]

def x_fxtwitter(u):
 m=re.search(r'/(?:i/)?([^/?#]+)/status/(\d+)',u)
 if not m:
  m2=re.search(r'/status/(\d+)',u)
  if not m2:raise RuntimeError('X post ID not found')
  user='i';pid=m2.group(1)
 else:user=m.group(1);pid=m.group(2)
 last=None
 for ep in (f'https://api.fxtwitter.com/{user}/status/{pid}',f'https://api.fxtwitter.com/2/status/{pid}',f'https://api.fxtwitter.com/{pid}'):
  try:
   r=cr.get(ep,headers={'User-Agent':UA,'Accept':'application/json'},impersonate='chrome',timeout=30);last=r.status_code
   if r.status_code!=200:continue
   d=r.json();st=d.get('status') or d.get('tweet') or d
   if not isinstance(st,dict):continue
   media=st.get('media') or {};ordered=media.get('all') or []
   if not ordered:ordered=(media.get('photos') or [])+(media.get('videos') or [])
   if not ordered:continue
   author=(st.get('author') or {}).get('name') or (st.get('author') or {}).get('screen_name') or 'X';txt=(st.get('text') or '').strip();title=f'{author} - {txt[:100]}' if txt else author;entries=[]
   for md in ordered:
    typ=md.get('type');src=md.get('url');w=md.get('width');h=md.get('height')
    if typ in ('photo','mosaic_photo') and src:
     entries.append({'title':title,'url':src,'_download_url':src,'thumbnail':src,'width':w,'height':h,'ext':(md.get('format') or Path(urlparse(src).path).suffix.lstrip('.') or 'jpg')})
    elif typ in ('video','gif'):
     fm=[]
     for f in md.get('formats') or []:
      fu=f.get('url')
      if fu and (f.get('container') in (None,'mp4') or '.mp4' in urlparse(fu).path):fm.append({'url':fu,'ext':'mp4','vcodec':'h264','acodec':'aac','tbr':(f.get('bitrate') or 0)/1000 or None,'height':f.get('height') or h,'width':f.get('width') or w,'filesize':f.get('size')})
     fm.sort(key=lambda f:(f.get('height') or 0,f.get('tbr') or 0),reverse=True);best=(fm[0]['url'] if fm else src)
     if best:entries.append({'title':title,'url':best,'_download_url':best,'thumbnail':md.get('thumbnail_url'),'width':w,'height':h,'duration':md.get('duration'),'filesize':md.get('filesize'),'ext':'mp4','formats':fm})
   if entries:return {'title':title,'entries':entries}
  except Exception:continue
 raise RuntimeError(f'X public metadata unavailable ({last})')
def x_syndication(u):
 m=re.search(r'/status/(\d+)',u)
 if not m:raise RuntimeError('X post ID not found')
 r=cr.get(f'https://cdn.syndication.twimg.com/tweet-result?id={m.group(1)}&lang=en',headers={'User-Agent':UA,'Accept':'application/json'},impersonate='chrome',timeout=30)
 if r.status_code!=200:raise RuntimeError('X syndication unavailable')
 d=r.json();media=d.get('mediaDetails') or []
 if not media:raise RuntimeError('No public X media found')
 usr=d.get('user') or {};txt=(d.get('text') or '').strip();author=usr.get('name') or usr.get('screen_name') or 'X';title=f'{author} - {txt[:100]}' if txt else author;entries=[]
 for md in media:
  typ=md.get('type');thumb=md.get('media_url_https') or md.get('media_url');orig=md.get('original_info') or {}
  if typ=='photo' and thumb:
   src=thumb+('&' if '?' in thumb else '?')+'name=orig';entries.append({'title':title,'url':src,'_download_url':src,'thumbnail':src,'width':orig.get('width'),'height':orig.get('height'),'ext':'jpg'})
  elif typ in ('video','animated_gif'):
   vs=[v for v in ((md.get('video_info') or {}).get('variants') or []) if v.get('content_type')=='video/mp4' and v.get('url')];vs.sort(key=lambda v:v.get('bitrate') or 0,reverse=True)
   if vs:
    fm=[{'url':v['url'],'ext':'mp4','vcodec':'h264','acodec':'aac','tbr':(v.get('bitrate') or 0)/1000 or None,'height':orig.get('height'),'width':orig.get('width')} for v in vs];entries.append({'title':title,'url':vs[0]['url'],'_download_url':vs[0]['url'],'thumbnail':thumb,'width':orig.get('width'),'height':orig.get('height'),'duration':((md.get('video_info') or {}).get('duration_millis') or 0)/1000 or None,'ext':'mp4','formats':fm})
 if not entries:raise RuntimeError('No public X media found')
 return {'title':title,'entries':entries}

def reddit_public(u):
 m=re.search(r'/comments/([^/?#]+)',u)
 if not m:raise RuntimeError('Reddit post ID not found')
 pid=m.group(1);payload=None
 for ep in (f'https://www.reddit.com/comments/{pid}.json?raw_json=1&include_over_18=on',f'https://old.reddit.com/comments/{pid}.json?raw_json=1&include_over_18=on'):
  try:
   r=cr.get(ep,headers={'User-Agent':UA,'Accept':'application/json'},impersonate='chrome',timeout=30)
   if r.status_code==200:payload=r.json();break
  except:pass
 if not payload:raise RuntimeError('Reddit public metadata unavailable')
 p=payload[0]['data']['children'][0]['data'];title=p.get('title') or 'Reddit media'
 if p.get('gallery_data') and p.get('media_metadata'):
  es=[];meta=p['media_metadata']
  for it in p['gallery_data'].get('items',[]):
   s=(meta.get(it.get('media_id'),{}).get('s') or {});src=(s.get('u') or s.get('gif') or s.get('mp4') or '').replace('&amp;','&')
   if src:es.append({'title':title,'url':src,'_download_url':src,'thumbnail':src,'width':s.get('x'),'height':s.get('y'),'ext':Path(urlparse(src).path).suffix.lstrip('.') or 'jpg'})
  if es:return {'title':title,'entries':es}
 mp=p
 if not ((p.get('secure_media') or p.get('media') or {}).get('reddit_video')) and p.get('crosspost_parent_list'):mp=p['crosspost_parent_list'][0]
 media=mp.get('secure_media') or mp.get('media') or {};rv=media.get('reddit_video') or (mp.get('preview') or {}).get('reddit_video_preview') or {};src=rv.get('dash_url') or rv.get('hls_url') or rv.get('fallback_url')
 if not src:
  direct=mp.get('url_overridden_by_dest') or mp.get('url')
  if direct and ('v.redd.it' in direct or urlparse(direct).path.lower().endswith(('.mp4',)+IMAGE_EXTS)):src=direct
 if not src:raise RuntimeError('No Reddit media URL found')
 try:i=ytdlp(src)
 except:i={'formats':[],'ext':'mp4' if 'v.redd.it' in src else Path(urlparse(src).path).suffix.lstrip('.') or None}
 i=i or {'formats':[]};i.update({'title':title,'_download_url':src});i['width']=i.get('width') or rv.get('width');i['height']=i.get('height') or rv.get('height');i['duration']=i.get('duration') or rv.get('duration');return i

def best_public_x(u):
 candidates=[]
 for fn in (ytdlp,x_fxtwitter,x_syndication):
  try:candidates.append(fn(u))
  except:pass
 if not candidates:raise RuntimeError('X extraction unavailable')
 return max(candidates,key=lambda x:len(flat(x)))
def extract(u):
 p=platform(u)
 if p=='X / Twitter':return best_public_x(u)
 if p=='Reddit':
  candidates=[]
  for fn in (ytdlp,reddit_public):
   try:candidates.append(fn(u))
   except:pass
  if not candidates:raise RuntimeError('Reddit extraction unavailable')
  return max(candidates,key=lambda x:len(flat(x)))
 return ytdlp(u)
def qualities(i):
 hs={}
 for f in i.get('formats') or []:
  h=f.get('height');t=f.get('tbr') or 0
  if h and f.get('vcodec') not in (None,'none') and (h not in hs or t>hs[h]['tbr']):hs[h]={'label':f'{h}p','height':h,'tbr':t}
 if not hs and i.get('height'):h=int(i['height']);hs[h]={'label':f'{h}p','height':h,'tbr':0}
 return [hs[h] for h in sorted(hs,reverse=True)][:10]
def safe_label(v):
 v=re.sub(r'[^A-Za-z0-9._-]+','_',str(v or '').strip().lstrip('@')).strip('._-')
 return (v[:48] or 'media')
def creator_name(post,i):
 for k in ('uploader_id','uploader','channel_id','channel','creator','artist','author'):
  if i.get(k):return safe_label(i.get(k))
 parts=[x for x in urlparse(post).path.split('/') if x]
 p=platform(post)
 if p=='X / Twitter' and parts and parts[0] not in ('i','status'):return safe_label(parts[0])
 return 'instagram' if p=='Instagram' else ('reddit' if p=='Reddit' else 'media')
def item(post,i,n):
 fm=i.get('formats') or [];typ='video' if any(f.get('vcodec') not in (None,'none') for f in fm) or i.get('duration') or str(i.get('ext','')).lower() in ('mp4','webm','mov') else 'image';src=i.get('_download_url') or i.get('webpage_url') or i.get('url') or post;creator=creator_name(post,i)
 return {'index':n,'title':i.get('title') or f'Media {n+1}','thumbnail':i.get('thumbnail') or (src if typ=='image' else None),'duration':i.get('duration'),'width':i.get('width'),'height':i.get('height'),'filesize':i.get('filesize') or i.get('filesize_approx'),'media_type':typ,'qualities':qualities(i),'token':sign({'url':post,'source':src,'index':n,'creator':creator,'exp':time.time()+900})}
def public_info(u,i):
 its=[item(u,x,n) for n,x in enumerate(flat(i))];return {'platform':platform(u),'title':i.get('title') or (its[0]['title'] if its else 'Media'),'count':len(its),'items':its}
def friendly(e):
 m=str(e).lower()
 if any(x in m for x in ('login','cookie','sign in','authentication','challenge')):return 401,'This public post is currently being served behind a platform login/session requirement.'
 if any(x in m for x in ('private','deleted','unavailable')):return 404,'This post is private, deleted, or unavailable.'
 return 422,'Could not analyze this public post right now.'
def direct_file(s):return urlparse(s).path.lower().endswith(DIRECT_EXTS)
def download_one(p,d,mode='best',height=None,prefix='media'):
 s=p.get('source') or p['url'];stamp=time.strftime('%Y-%m-%d_%H%M%S',time.localtime());stem=f"{safe_label(p.get('creator') or 'media')}_{stamp}_{int(p.get('index',0))+1:02d}"
 if direct_file(s):
  ext=Path(urlparse(s).path).suffix or '.bin';t=Path(d)/(stem+ext);r=cr.get(s,headers={'User-Agent':UA},impersonate='chrome',timeout=120)
  if r.status_code!=200:raise RuntimeError(f'Direct media download failed ({r.status_code})')
  t.write_bytes(r.content);return t
 fmt='bestaudio/best' if mode=='audio' else (f'bestvideo*[height<={height}]+bestaudio/best[height<={height}]/best' if mode=='quality' and height else 'bestvideo*+bestaudio/best');o,c=opts(True,str(Path(d)/(stem+'.%(ext)s')),fmt)
 if mode=='audio':o['postprocessors']=[{'key':'FFmpegExtractAudio','preferredcodec':'m4a','preferredquality':'0'}]
 try:
  with yt_dlp.YoutubeDL(o) as y:y.download([s])
  fs=[x for x in Path(d).iterdir() if x.is_file() and x.name.startswith(stem)]
  if not fs:raise RuntimeError('Download failed')
  return max(fs,key=lambda x:x.stat().st_size)
 finally:
  if c:
   try:os.remove(c)
   except:pass
@app.get('/health')
def health():return {'ok':True,'yt_dlp':yt_dlp.version.__version__,'ffmpeg':bool(FFMPEG),'multi_media':True,'public_sensitive_media':True,'x_fallback':'fxtwitter+syndication'}
@app.post('/api/analyze')
def analyze(r:AnalyzeRequest):
 u=r.url.strip()
 if not valid(u):raise HTTPException(400,'Use a public Instagram, X / Twitter, or Reddit link.')
 try:i=extract(u)
 except Exception as e:
  c,d=friendly(e);raise HTTPException(c,d)
 if not i:raise HTTPException(404,'No downloadable media found.')
 return public_info(u,i)
@app.get('/api/download')
def download(background_tasks:BackgroundTasks,token:str=Query(...),mode:str=Query('best',pattern='^(best|audio|quality)$'),height:int|None=Query(None,ge=1,le=4320)):
 p=unsign(token);d=tempfile.mkdtemp(prefix='media-dl-')
 try:
  t=download_one(p,d,mode,height,'media');background_tasks.add_task(shutil.rmtree,d,True);return FileResponse(t,filename=t.name,media_type='application/octet-stream')
 except Exception as e:
  shutil.rmtree(d,ignore_errors=True);c,x=friendly(e);raise HTTPException(c,x)
@app.post('/api/download-batch')
def batch(r:BatchRequest,background_tasks:BackgroundTasks):
 if not r.tokens or len(r.tokens)>30:raise HTTPException(400,'Nothing to download.')
 d=tempfile.mkdtemp(prefix='media-batch-');fs=[]
 try:
  for n,t in enumerate(r.tokens):fs.append(download_one(unsign(t),d,'best',None,f'media-{n+1:02d}'))
  z=Path(d)/'media-downloader.zip'
  with zipfile.ZipFile(z,'w',zipfile.ZIP_DEFLATED) as a:
   for f in fs:a.write(f,arcname=f.name)
  background_tasks.add_task(shutil.rmtree,d,True);return FileResponse(z,filename='media-downloader.zip',media_type='application/zip')
 except Exception as e:
  shutil.rmtree(d,ignore_errors=True);c,x=friendly(e);raise HTTPException(c,x)
@app.get('/manifest.webmanifest')
def manifest():return FileResponse(ROOT/'manifest.webmanifest',media_type='application/manifest+json')
@app.get('/sw.js')
def sw():return FileResponse(ROOT/'sw.js',media_type='application/javascript',headers={'Cache-Control':'no-cache'})
@app.get('/icon.svg')
def icon():return FileResponse(ROOT/'icon.svg',media_type='image/svg+xml')
@app.get('/',response_class=HTMLResponse)
def home():return (ROOT/'index.html').read_text(encoding='utf-8')