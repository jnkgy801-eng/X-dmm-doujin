"""
💰📸 DMMアフィリエイト → Instagram 自動投稿スクリプト
GitHub Actions で定期的に自動実行されます。
"""

import os
import sys
import re
import json
import time
import io
import base64
import urllib.parse
import requests
from PIL import Image, ImageDraw, ImageFont

# ================================================================
# ⚙️  設定（環境変数から読み込み）
# ================================================================

ACCESS_TOKEN   = os.environ.get('META_ACCESS_TOKEN', '')
IG_USER_ID     = os.environ.get('INSTAGRAM_ACCOUNT_ID', '')
IMGBB_API_KEY  = os.environ.get('IMGBB_API_KEY', '')
DMM_API_ID     = os.environ.get('DMM_API_ID', '')       # DMMアフィリエイトAPI ID
DMM_AFFILIATE_ID = os.environ.get('DMM_AFFILIATE_ID', '')  # アフィリエイトID（例: xxxxx-990）

if not ACCESS_TOKEN or not IG_USER_ID:
    print('❌ 環境変数 META_ACCESS_TOKEN / INSTAGRAM_ACCOUNT_ID が設定されていません。')
    sys.exit(1)

if not DMM_API_ID or not DMM_AFFILIATE_ID:
    print('❌ 環境変数 DMM_API_ID / DMM_AFFILIATE_ID が設定されていません。')
    sys.exit(1)

print('✅ 認証情報を読み込みました。')

# ================================================================
# ⚙️  投稿設定
# ================================================================

# 取得する商品カテゴリ設定
# floor指定値: videoa=一般動画, videoc=素人動画, anime=アニメ, doujin=同人, comic=電子書籍, goods=グッズ
DMM_FLOOR = os.environ.get('DMM_FLOOR', 'digital')   # ymlのデフォルトに合わせる
DMM_SORT  = os.environ.get('DMM_SORT', '-date')       # 新着降順に統一
DMM_HITS      = int(os.environ.get('DMM_HITS', '20'))    # 取得件数（最大100）


# フロアごとのservice対応表（DMM APIの仕様に合わせた正しい組み合わせ）
FLOOR_SERVICE_MAP = {
    'videoa':  ('digital', 'videoa'),
    'videoc':  ('digital', 'videoc'),
    'anime':   ('digital', 'anime'),
    'doujin':  ('doujin',  'digital_doujin'),
    'comic':   ('ebook',   'comic'),
    'goods':   ('mono',    'goods'),
    'digital': ('digital', 'videoa'),   # ← これを追加（ymlのデフォルト対応）
}

POST_ALL      = os.environ.get('POST_ALL', 'false').lower() == 'true'
POST_INDEX    = int(os.environ.get('POST_INDEX', '0'))
INTERVAL      = int(os.environ.get('INTERVAL', '30'))    # 複数投稿時の待機秒数

BASE_URL      = 'https://graph.facebook.com/v19.0'
DMM_API_BASE  = 'https://api.dmm.com/affiliate/v3'

# カテゴリ別ハッシュタグ
HASHTAG_MAP = {
    'videoa': '#動画 #アダルト #FANZA #DMM #PR #アフィリエイト #おすすめ #新着',
    'videoc': '#素人 #動画 #FANZA #DMM #PR #アフィリエイト #おすすめ #新着',
    'anime':  '#アニメ #FANZA #DMM #PR #アフィリエイト #おすすめ #新着',
    'doujin': '#同人 #FANZA #DMM #PR #アフィリエイト #おすすめ #新着',
    'comic':  '#電子書籍 #漫画 #DMM #PR #アフィリエイト #おすすめ #新着',
    'goods':  '#通販 #グッズ #DMM #PR #アフィリエイト #おすすめ #新着',
    'default': '#DMM #PR #アフィリエイト #おすすめ #新着',
}

# ================================================================
# 🔧 DMM API 関数
# ================================================================

def fetch_dmm_products(floor=DMM_FLOOR, hits=DMM_HITS, sort=DMM_SORT):
    """DMMアフィリエイトAPIから商品一覧を取得"""
    service, floor_name = FLOOR_SERVICE_MAP.get(floor, ('digital', floor))
    params = {
        'api_id':       DMM_API_ID,
        'affiliate_id': DMM_AFFILIATE_ID,
        'site':         'FANZA',
        'service':      service,
        'floor':        floor_name,
        'hits':         hits,
        'sort':         sort,
        'output':       'json',
    }
    try:
        resp = requests.get(f'{DMM_API_BASE}/ItemList', params=params, timeout=15)
        data = resp.json()
        items = data.get('result', {}).get('items', [])
        if isinstance(items, dict):
            items = items.get('item', [])
        print(f'  ✅ {len(items)} 件の商品を取得しました。')
        return items
    except Exception as e:
        print(f'  ❌ DMM APIエラー: {e}')
        return []


def parse_product(item):
    """APIレスポンスから必要な情報を抽出"""
    title       = item.get('title', '')
    affiliate_url = item.get('affiliateURL', '') or item.get('URL', '')
    # 商品画像（大サイズ優先）
    image_url   = (item.get('imageURL') or {}).get('large') \
               or (item.get('imageURL') or {}).get('small') \
               or ''
    # 価格
    prices      = item.get('prices', {})
    price_str   = ''
    if prices:
        price_val = prices.get('price') or prices.get('list_price') or ''
        if price_val:
            price_num = ''.join(c for c in str(price_val) if c.isdigit())
            price_str = f'¥{int(price_num):,}' if price_num else ''
    # 出演者・ジャンル
    actors  = [a.get('name', '') for a in (item.get('iteminfo', {}).get('actress') or [])][:3]
    genres  = [g.get('name', '') for g in (item.get('iteminfo', {}).get('genre') or [])][:3]
    maker   = ((item.get('iteminfo', {}).get('maker') or [{}])[0]).get('name', '')

    return {
        'title':         title,
        'affiliate_url': affiliate_url,
        'image_url':     image_url,
        'price':         price_str,
        'actors':        actors,
        'genres':        genres,
        'maker':         maker,
    }


# ================================================================
# 🖼️  画像処理関数
# ================================================================

def download_image_as_pil(url, timeout=30):
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (compatible; AffiliateBot/1.0)'}
        resp = requests.get(url, headers=headers, timeout=timeout, stream=True)
        if resp.status_code == 200 and 'image' in resp.headers.get('Content-Type', ''):
            return Image.open(io.BytesIO(resp.content)).convert('RGB')
    except Exception as e:
        print(f'    ⚠️ 画像ダウンロードエラー: {e}')
    return None


def add_pr_badge(pil_img):
    """画像右上にPRバッジを追加"""
    draw = ImageDraw.Draw(pil_img)
    W, H = pil_img.size
    badge_w, badge_h = 120, 50
    x0, y0 = W - badge_w - 20, 20
    draw.rounded_rectangle([x0, y0, x0+badge_w, y0+badge_h], radius=8, fill='#e11d48')
    try:
        font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 26)
    except Exception:
        font = ImageFont.load_default()
    draw.text((x0 + badge_w//2, y0 + badge_h//2), 'PR', font=font,
              fill='white', anchor='mm')
    return pil_img


def make_square_padded(pil_img, size=1080, bg_color='#111111'):
    """画像を1080x1080の正方形にパディング"""
    img = pil_img.copy()
    img.thumbnail((size, size), Image.LANCZOS)
    canvas = Image.new('RGB', (size, size), bg_color)
    offset = ((size - img.width) // 2, (size - img.height) // 2)
    canvas.paste(img, offset)
    return canvas


def generate_fallback_card(product):
    """商品画像が取得できない場合のフォールバックカード"""
    W, H = 1080, 1080
    img  = Image.new('RGB', (W, H), '#111827')
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, 0, W, 10], fill='#e11d48')
    draw.rectangle([0, H-10, W, H], fill='#e11d48')
    try:
        f_large  = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 52)
        f_medium = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 34)
        f_small  = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 26)
    except Exception:
        f_large = f_medium = f_small = ImageFont.load_default()

    # タイトル折り返し
    lines, line, max_w = [], '', W - 120
    for ch in product['title']:
        test = line + ch
        bbox = draw.textbbox((0, 0), test, font=f_large)
        if bbox[2] - bbox[0] > max_w:
            lines.append(line); line = ch
        else:
            line = test
    if line: lines.append(line)
    y = 180
    for ln in lines[:5]:
        draw.text((60, y), ln, font=f_large, fill='white'); y += 68

    if product['price']:
        draw.text((60, y + 30), f"💰 {product['price']}", font=f_medium, fill='#fbbf24')
        y += 70
    if product['maker']:
        draw.text((60, y + 10), f"🏷 {product['maker']}", font=f_small, fill='#94a3b8')

    draw.rounded_rectangle([W-160, 20, W-20, 70], radius=8, fill='#e11d48')
    draw.text((W-90, 45), 'PR', font=f_medium, fill='white', anchor='mm')
    draw.text((60, H-70), '💰 DMMアフィリエイト', font=f_small, fill='#475569')
    return img


def upload_to_imgbb(pil_img, api_key):
    if not api_key:
        return None
    buf = io.BytesIO()
    pil_img.save(buf, format='JPEG', quality=90)
    b64 = base64.b64encode(buf.getvalue()).decode()
    try:
        resp = requests.post('https://api.imgbb.com/1/upload',
                             data={'key': api_key, 'image': b64}, timeout=30)
        result = resp.json()
        if result.get('success'):
            return result['data']['url']
    except Exception as e:
        print(f'    ❌ imgbbアップロードエラー: {e}')
    return None


def get_uploadable_image_url(product):
    """商品画像を取得・加工してアップロード可能なURLを返す"""
    img_url = product.get('image_url', '')

    pil = None
    if img_url and img_url.startswith('http'):
        print(f'    🖼️  商品画像をダウンロード中...')
        pil = download_image_as_pil(img_url)

    if pil:
        pil = make_square_padded(pil)
        pil = add_pr_badge(pil)
        print(f'    ✅ 商品画像の加工完了')
    else:
        print(f'    🎨 フォールバックカードを生成中...')
        pil = generate_fallback_card(product)

    if IMGBB_API_KEY:
        print(f'    ☁️  imgbbにアップロード中...')
        url = upload_to_imgbb(pil, IMGBB_API_KEY)
        if url:
            print(f'    ✅ アップロード成功: {url}')
            return url
        print('    ❌ imgbbアップロード失敗')
    else:
        print('    ⚠️  IMGBB_API_KEY 未設定のため画像投稿をスキップします。')

    return None


# ================================================================
# 📝 キャプション生成
# ================================================================

def build_caption(product):
    hashtags = HASHTAG_MAP.get(DMM_FLOOR, HASHTAG_MAP['default'])

    genre_text = '　'.join(product['genres']) if product['genres'] else ''
    actor_text = '　'.join(product['actors']) if product['actors'] else ''

    lines = [f"🎬 {product['title']}\n"]
    if product['price']:
        lines.append(f"💰 価格: {product['price']}")
    if product['maker']:
        lines.append(f"🏷 メーカー: {product['maker']}")
    if actor_text:
        lines.append(f"👤 出演: {actor_text}")
    if genre_text:
        lines.append(f"🎞 ジャンル: {genre_text}")

    lines.append('')
    lines.append('━━━━━━━━━━━━━━━')
    lines.append('✅ 詳細・購入はプロフィールのリンクから👆')
    if product['affiliate_url']:
        lines.append(f"🔗 {product['affiliate_url']}")
    lines.append('━━━━━━━━━━━━━━━')
    lines.append('')
    lines.append('※本投稿はアフィリエイト広告を含みます。')
    lines.append('')
    lines.append(hashtags)

    return '\n'.join(lines)


# ================================================================
# 📤 Instagram投稿関数
# ================================================================

def create_media_container(image_url, caption):
    resp = requests.post(
        f'{BASE_URL}/{IG_USER_ID}/media',
        data={
            'image_url':  image_url,
            'caption':    caption,
            'media_type': 'IMAGE',
            'access_token': ACCESS_TOKEN,
        }
    )
    data = resp.json()
    if resp.status_code == 200 and 'id' in data:
        print(f'  ✅ メディアコンテナ作成: ID={data["id"]}')
        print('  ⏳ 処理待機中（10秒）...')
        time.sleep(10)
        return data['id']
    print('  ❌ コンテナ作成失敗:')
    print(json.dumps(data, indent=2, ensure_ascii=False))
    return None


def publish_media(container_id):
    resp = requests.post(
        f'{BASE_URL}/{IG_USER_ID}/media_publish',
        data={'creation_id': container_id, 'access_token': ACCESS_TOKEN}
    )
    data = resp.json()
    if resp.status_code == 200 and 'id' in data:
        print(f'  🎉 投稿成功！ 投稿ID={data["id"]}')
        return data['id']
    print('  ❌ 投稿失敗:')
    print(json.dumps(data, indent=2, ensure_ascii=False))
    return None


def post_to_instagram(image_url, caption):
    print('=' * 55)
    print('📤 Instagram投稿開始...')
    print(f'  画像URL: {image_url[:70]}...')
    print(f'  キャプション先頭: {caption[:50]}...')
    print('=' * 55)
    if not image_url or not image_url.startswith('http'):
        print('❌ 有効な画像URLがありません。')
        return None
    cid = create_media_container(image_url, caption)
    if not cid:
        return None
    pid = publish_media(cid)
    if pid:
        print('\n✨ 投稿完了！Instagramアプリで確認してください。')
    return pid


# ================================================================
# 🚀 メイン実行
# ================================================================

print(f'🛍️  DMMから商品情報を取得中（フロア: {DMM_FLOOR} / ソート: {DMM_SORT}）...')
raw_items = fetch_dmm_products()

if not raw_items:
    print('❌ 商品が1件も取得できませんでした。')
    sys.exit(1)

products = [parse_product(item) for item in raw_items]
print(f'\n合計 {len(products)} 件の商品を処理します。\n')

# 画像を取得・アップロード
print('🖼️  画像を取得・処理中...')
for p in products:
    print(f"  [{p['maker'] or 'DMM'}] {p['title'][:35]}...")
    p['resolved_image_url'] = get_uploadable_image_url(p)

# 投稿
print('\n📤 Instagramへ投稿中...')

if POST_ALL:
    targets = [p for p in products if p.get('resolved_image_url')]
    print(f'  {len(targets)} 件を順番に投稿します。')
    for idx, product in enumerate(targets, 1):
        print(f'\n  [{idx}/{len(targets)}] {product["title"][:40]}...')
        post_to_instagram(product['resolved_image_url'], build_caption(product))
        if idx < len(targets):
            print(f'  ⏳ {INTERVAL}秒待機中...')
            time.sleep(INTERVAL)
    print('\n🏁 全投稿完了！')
else:
    if POST_INDEX >= len(products):
        print(f'❌ POST_INDEX={POST_INDEX} が範囲外です（0〜{len(products)-1}）')
        sys.exit(1)
    product = products[POST_INDEX]
    img_url = product.get('resolved_image_url')
    print(f'  選択: [{POST_INDEX}] {product["title"]}')
    if not img_url:
        print('  ❌ 有効な画像URLがありません。')
        sys.exit(1)
    post_to_instagram(img_url, build_caption(product))
