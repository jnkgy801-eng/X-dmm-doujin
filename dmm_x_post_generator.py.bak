"""
💰🐦 DMMアフィリエイト → X（Twitter）投稿文ジェネレーター
DMMから商品情報を取得し、X投稿用テキストをデスクトップまたは指定フォルダに保存します。
（X APIは使わないので完全無料で動作します）
"""

import os
import sys
import datetime
import requests
import random
from pathlib import Path

# ================================================================
# ⚙️  設定（環境変数から読み込み）
# ================================================================

DMM_API_ID       = os.environ.get('DMM_API_ID', '')
DMM_AFFILIATE_ID = os.environ.get('DMM_AFFILIATE_ID', '')

if not DMM_API_ID or not DMM_AFFILIATE_ID:
    print('❌ 環境変数 DMM_API_ID / DMM_AFFILIATE_ID が設定されていません。')
    sys.exit(1)

print('✅ 認証情報を読み込みました。')

DMM_FLOOR = os.environ.get('DMM_FLOOR', 'videoa')

# ----------------------------------------------------------------
# 📌 ソートモード設定
#    DMM_SORT_MODE=both（デフォルト）→ 新着20件 ＋ 人気20件 = 計40件を1ファイルに保存
#    DMM_SORT_MODE=date              → 新着順のみ20件
#    DMM_SORT_MODE=rank              → 人気順のみ20件
# ----------------------------------------------------------------
DMM_SORT_MODE = os.environ.get('DMM_SORT_MODE', 'both').lower()

SORT_TARGETS = {
    'both': [('-date', '新着順'), ('-rank', '人気順')],
    'date': [('-date', '新着順')],
    'rank': [('-rank', '人気順')],
}
SORT_LIST = SORT_TARGETS.get(DMM_SORT_MODE, SORT_TARGETS['both'])

# ----------------------------------------------------------------
# 🎲 取得開始位置（環境変数未設定時はランダム: 1〜480）
# ----------------------------------------------------------------
_raw_start = os.environ.get('POST_START_INDEX', '')
if _raw_start.strip().isdigit():
    POST_START_INDEX = int(_raw_start.strip())
    print(f'📌 指定された取得開始番号: {POST_START_INDEX}')
else:
    POST_START_INDEX = random.randint(1, 480)
    print(f'🎲 ランダム取得開始番号: {POST_START_INDEX}')

FETCH_COUNT = 100
DMM_OFFSET  = POST_START_INDEX
DMM_HITS    = FETCH_COUNT

# ----------------------------------------------------------------
# 💰 価格フィルター設定
#    DMM_PRICE_RANGE=all（デフォルト）→ 価格による絞り込みなし
#    その他の指定例:
#      "0-999"    → 0円〜999円
#      "1000-1999"→ 1000円〜1999円
#      "2000-2999"→ 2000円〜2999円
#      "3000-4999"→ 3000円〜4999円
#      "5000-"    → 5000円以上
# ----------------------------------------------------------------
DMM_PRICE_RANGE = os.environ.get('DMM_PRICE_RANGE', 'all').strip().lower()

def parse_price_range(range_str):
    """価格範囲文字列を (min, max) のタプルに変換する。max=Noneは上限なし。"""
    if not range_str or range_str == 'all':
        return None
    range_str = range_str.replace('円', '').replace(',', '').strip()
    if '-' not in range_str:
        return None
    min_part, max_part = range_str.split('-', 1)
    min_part = min_part.strip()
    max_part = max_part.strip()
    try:
        price_min = int(min_part) if min_part else 0
    except ValueError:
        price_min = 0
    if max_part:
        try:
            price_max = int(max_part)
        except ValueError:
            price_max = None
    else:
        price_max = None
    return (price_min, price_max)

PRICE_RANGE_BOUNDS = parse_price_range(DMM_PRICE_RANGE)
if PRICE_RANGE_BOUNDS:
    _pmin, _pmax = PRICE_RANGE_BOUNDS
    _pmax_label = f'{_pmax:,}円' if _pmax is not None else '上限なし'
    print(f'💰 価格フィルター: {_pmin:,}円 〜 {_pmax_label}')
else:
    print('💰 価格フィルター: なし（すべての価格を対象）')

DMM_API_BASE = 'https://api.dmm.com/affiliate/v3'

FLOOR_SERVICE_MAP = {
    'videoa':  ('digital', 'videoa'),
    'videoc':  ('digital', 'videoc'),
    'anime':   ('digital', 'anime'),
    'doujin':  ('doujin',  'digital_doujin'),
    'comic':   ('ebook',   'comic'),
    'goods':   ('mono',    'goods'),
    'digital': ('digital', 'videoa'),
}

HASHTAG_MAP = {
    'videoa': '#FANZA #DMM #アダルト #PR',
    'videoc': '#FANZA #DMM #素人 #PR',
    'anime':  '#FANZA #DMM #アニメ #PR',
    'doujin': '#FANZA #DMM #同人 #PR',
    'comic':  '#DMM #電子書籍 #漫画 #PR',
    'goods':  '#DMM #グッズ #PR',
    'default': '#DMM #PR',
}

# ================================================================
# 🤖 AI動的コピー生成（タイトル・ジャンルに合わせた人間味ある一言）
# ================================================================

# Anthropic APIキー（環境変数から取得）
ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY', '')

# AI生成が使えない場合のフォールバック用ジャンル別テンプレート
COPY_TEMPLATES_BY_GENRE = {
    'ラブコメ': [
        "ニヤニヤが止まらない展開…深夜に読む系😂",
        "これはニヤニヤ不可避の神展開だ😍",
        "ラブコメ好きにはたまらん一冊です💕",
    ],
    '巨乳': [
        "これは…ボリューム感が正義ですね😳",
        "わかってる作品。好きです。",
    ],
    '人妻・主婦': [
        "禁断の甘さがクセになる設定だ…🌙",
        "こういう背徳感、なかなか抜け出せない😅",
    ],
    '制服': [
        "学園ものは安定の良さがある📚",
        "ジャンルの王道をきちんと押さえてます✏️",
    ],
    '熟女': [
        "大人の色気って言葉がぴったりな作品💋",
        "熟女好きに刺さる一冊、間違いなし",
    ],
    '近親相姦': [
        "タブー設定が好きな人にはツボすぎる構成…",
        "ストーリーの引きが強すぎてやばい",
    ],
    'NTR・寝取られ': [
        "メンタルにくる系が好きな人に👁",
        "NTR耐性ある人ならドはまり確定",
    ],
    '調教': [
        "この展開の流れ、読んでてテンション上がる🔥",
        "こういう一冊、定期的に読みたくなる",
    ],
    '中出し': [
        "内容の濃さがしっかりある作品です",
        "このジャンルでこのクオリティは普通に高い",
    ],
    '異種姦': [
        "ファンタジー系が好きならドハマり注意🐉",
        "世界観の作り込みが好きすぎる…",
    ],
}

COPY_TEMPLATES_FALLBACK = [
    "タイトルで気になった人はそのまま突撃で👇",
    "深夜にひっそり楽しむやつ、これです🌙",
    "なんか知らんけど好きなやつ、これ😂",
    "ジャンル好きなら刺さる一冊です",
    "こういうの待ってた人いるんじゃないかな👀",
    "読んでみたら予想以上だった系の作品",
    "タイトル通りの内容でちゃんと満足できる",
    "コレ系好きなら後悔しない一冊だと思う",
    "説明より読んだ方が早い作品です🔥",
    "深夜のお供にちょうどいい密度感🌙",
]


def get_copy_ai(title: str, genres: list, maker: str, price: str) -> str:
    """Claude APIを使ってタイトル・ジャンルに合った自然な複数行コメントを生成する。
    API失敗時はフォールバックテンプレートを返す。"""
    if not ANTHROPIC_API_KEY:
        return _get_copy_fallback(genres)

    genre_str = '・'.join(genres) if genres else 'なし'
    maker_str = maker if maker else '不明'
    price_str = price if price else '不明'
    prompt = (
        f"同人誌（エロ同人）のX(Twitter)アフィリエイト投稿の「紹介本文」を作ってください。\n\n"
        f"作品タイトル：{title}\n"
        f"ジャンル：{genre_str}\n"
        f"サークル/メーカー：{maker_str}\n"
        f"価格：{price_str}\n\n"
        f"【条件】\n"
        f"- 全体で60〜90文字（改行込み）\n"
        f"- 2〜3行構成。1行目は作品の雰囲気や設定への反応、2行目以降はジャンル的な見どころや刺さるポイント\n"
        f"- AIっぽい宣伝文句（「話題沸騰中」「クオリティに驚く」「ファン必見」「期間限定」等）は絶対使わない\n"
        f"- そのジャンルが好きな人が普通につぶやくような、自然な口語体\n"
        f"- 絵文字は全体で2〜3個まで。「！」「✨」の多用NG\n"
        f"- タイトルやジャンル・設定の内容に具体的に言及する\n"
        f"- 出力は本文テキストのみ。前置きや説明・カギカッコは不要。"
    )

    try:
        resp = requests.post(
            'https://api.anthropic.com/v1/messages',
            headers={
                'x-api-key': ANTHROPIC_API_KEY,
                'anthropic-version': '2023-06-01',
                'content-type': 'application/json',
            },
            json={
                'model': 'claude-haiku-4-5-20251001',
                'max_tokens': 150,
                'messages': [{'role': 'user', 'content': prompt}],
            },
            timeout=10,
        )
        data = resp.json()
        text = data.get('content', [{}])[0].get('text', '').strip()
        if text and len(text) <= 120:
            return text
    except Exception as e:
        print(f'    ⚠️  AI生成エラー（フォールバック使用）: {e}')

    return _get_copy_fallback(genres)


def _get_copy_fallback(genres: list) -> str:
    """ジャンルに合ったフォールバックテンプレートを返す。"""
    for genre in genres:
        for key, templates in COPY_TEMPLATES_BY_GENRE.items():
            if key in genre:
                return random.choice(templates)
    return random.choice(COPY_TEMPLATES_FALLBACK)

# ================================================================
# 🔧 DMM API 関数
# ================================================================

def fetch_dmm_products(sort_key, sort_label):
    service, floor_name = FLOOR_SERVICE_MAP.get(DMM_FLOOR, ('digital', 'videoa'))
    params = {
        'api_id':       DMM_API_ID,
        'affiliate_id': DMM_AFFILIATE_ID,
        'site':         'FANZA',
        'service':      service,
        'floor':        floor_name,
        'hits':         DMM_HITS,
        'offset':       DMM_OFFSET,
        'sort':         sort_key,
        'output':       'json',
    }
    print(f'\n  [{sort_label}] 取得範囲: {DMM_OFFSET}件目〜{DMM_OFFSET + DMM_HITS - 1}件目')
    try:
        resp = requests.get(f'{DMM_API_BASE}/ItemList', params=params, timeout=15)
        data = resp.json()
        items = data.get('result', {}).get('items', [])
        if isinstance(items, dict):
            items = items.get('item', [])
        if items:
            url_str = items[0].get('affiliateURL', '')
            print(f"  URLの総文字数: {len(url_str)} / 末尾10文字: {url_str[-10:]}")
        print(f'  ✅ {len(items)} 件取得しました。')
        return items
    except Exception as e:
        print(f'  ❌ DMM APIエラー: {e}')
        return []


def parse_product(item):
    title         = item.get('title', '')
    affiliate_url = item.get('affiliateURL', '') or item.get('URL', '')
    prices        = item.get('prices', {})
    price_str     = ''
    price_num     = None
    if prices:
        price_val = prices.get('price') or prices.get('list_price') or ''
        if price_val:
            digits = ''.join(c for c in str(price_val) if c.isdigit())
            if digits:
                price_num = int(digits)
                price_str = f'\u00a5{price_num:,}'
    actors = [a.get('name', '') for a in (item.get('iteminfo', {}).get('actress') or [])][:3]
    genres = [g.get('name', '') for g in (item.get('iteminfo', {}).get('genre') or [])][:3]
    maker  = ((item.get('iteminfo', {}).get('maker') or [{}])[0]).get('name', '')

    sample_movie_url = ''
    smv = item.get('sampleMovieURL', {})
    if smv:
        for key in ['size_720_480', 'size_644_414', 'size_560_360', 'size_476_306']:
            val = smv.get(key, '')
            if val:
                sample_movie_url = val.strip()
                break

    return {
        'title':            title,
        'affiliate_url':    affiliate_url,
        'price':            price_str,
        'price_num':        price_num,
        'actors':           actors,
        'genres':           genres,
        'maker':            maker,
        'sample_movie_url': sample_movie_url,
    }

def clean_url(url):
    if not url:
        return ''
    url = url.strip().replace('\n', '').replace('\r', '').replace('　', '')
    if not url.startswith('http'):
        return ''
    return url


def actor_tags(actors):
    return '　'.join('#' + a.replace(' ', '').replace('　', '') for a in actors if a)


def genre_tags(genres):
    """ジャンル名（人妻・主婦、巨乳など）をハッシュタグ形式に変換する。"""
    return '　'.join('#' + g.replace(' ', '').replace('　', '') for g in genres if g)


def price_in_range(product):
    """価格フィルターが設定されている場合、商品の価格が範囲内かどうかを判定する。"""
    if not PRICE_RANGE_BOUNDS:
        return True
    price_num = product.get('price_num')
    if price_num is None:
        return False
    price_min, price_max = PRICE_RANGE_BOUNDS
    if price_num < price_min:
        return False
    if price_max is not None and price_num > price_max:
        return False
    return True


def build_x_post(product):
    hashtags = HASHTAG_MAP.get(DMM_FLOOR, HASHTAG_MAP['default'])
    url      = clean_url(product['affiliate_url'])
    sample   = clean_url(product.get('sample_movie_url', ''))
    act_tags = actor_tags(product['actors'])
    copy     = get_copy_ai(product['title'], product['genres'], product.get('maker', ''), product['price'])

    title = product['title']

    # ── ブロックを組み立て、280文字に収まるよう調整 ──────────────────
    # 各要素の文字コストを計算しながら貪欲に詰める

    def assemble(full_title, genre_limit, include_sample):
        lines = []
        # タイトル行
        lines.append(f"📖 {full_title}")
        lines.append('')
        # AI生成本文（複数行）
        lines.append(copy)
        lines.append('')
        # 価格
        if product['price']:
            lines.append(f"💰 {product['price']}")
        # メーカー/サークル
        if product.get('maker'):
            lines.append(f"🏷 {product['maker']}")
        # 出演者
        if act_tags:
            lines.append(f"👤 {act_tags}")
        # ジャンルタグ
        if product['genres']:
            lines.append(f"🎞 {genre_tags(product['genres'][:genre_limit])}")
        lines.append('')
        # URL
        lines.append(url)
        # サンプル動画
        if include_sample and sample:
            lines.append(f"▶ サンプル動画: {sample}")
        # ハッシュタグ
        lines.append(hashtags)
        return '\n'.join(lines)

    # まずフル構成（タイトル全表示・全ジャンル・サンプルあり）で試みる
    text = assemble(title, genre_limit=5, include_sample=True)

    # 280文字超えたらサンプルを外す
    if len(text) > 280:
        text = assemble(title, genre_limit=5, include_sample=False)

    # まだ超えたらジャンルを2つに絞る
    if len(text) > 280:
        text = assemble(title, genre_limit=2, include_sample=False)

    # それでも超えたらタイトルを40文字に切る
    if len(text) > 280:
        short_title = title[:40] + '…' if len(title) > 40 else title
        text = assemble(short_title, genre_limit=2, include_sample=False)

    return text

# ================================================================
# 💾 保存先を決定
# ================================================================

def get_save_dir():
    """
    保存先の優先順位:
    1. 環境変数 SAVE_DIR で明示指定されたパス
    2. GitHub Actions 環境 (SAVE_TO_REPO=true) → カレントディレクトリ（後でoutputsへ移動）
    3. デスクトップ（ローカル実行時）
       - ~/Desktop
       - ~/OneDrive/Desktop
       - ~/OneDrive/デスクトップ
       - ~/デスクトップ
    4. カレントディレクトリ（フォールバック）
    """
    # 環境変数で明示指定
    explicit = os.environ.get('SAVE_DIR', '').strip()
    if explicit:
        Path(explicit).mkdir(parents=True, exist_ok=True)
        return explicit

    # GitHub Actions上での実行（outputs/フォルダに保存）
    if os.environ.get('SAVE_TO_REPO', '').lower() == 'true':
        out = Path('outputs')
        out.mkdir(exist_ok=True)
        return str(out)

    # ローカル実行時はデスクトップを探す
    try:
        home = Path.home()
        for path in [
            home / "Desktop",
            home / "OneDrive" / "Desktop",
            home / "OneDrive" / "デスクトップ",
            home / "デスクトップ",
        ]:
            if path.exists():
                return str(path)
    except Exception:
        pass

    return '.'


def save_posts(all_sections):
    save_dir  = get_save_dir()
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    filename  = f'dmm_x_posts_{timestamp}.txt'
    filepath  = os.path.join(save_dir, filename)

    total = sum(len(posts) for _, posts in all_sections)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(f"# DMMアフィリエイト X投稿文\n")
        f.write(f"# 生成日時: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"# フロア: {DMM_FLOOR} / モード: {DMM_SORT_MODE}\n")
        f.write(f"# 価格フィルター: {DMM_PRICE_RANGE}\n")
        f.write(f"# 取得開始: {DMM_OFFSET}件目 / 各ソート{FETCH_COUNT}件\n")
        f.write(f"# 総投稿数: {total}件\n")
        f.write("=" * 60 + "\n\n")

        for sort_label, posts in all_sections:
            f.write(f"{'=' * 60}\n")
            f.write(f"【{sort_label}】{len(posts)}件\n")
            f.write(f"{'=' * 60}\n\n")

            for i, (product, text) in enumerate(posts, 1):
                f.write(f"--- {sort_label} {i}/{len(posts)} ---\n")
                f.write(f"商品名: {product['title']}\n")
                f.write(f"文字数: {len(text)}文字\n")
                f.write(f"URL確認: {product['affiliate_url']}\n")
                if product.get('sample_movie_url'):
                    f.write(f"サンプル動画: {product['sample_movie_url']}\n")
                f.write("-" * 40 + "\n")
                f.write(text)
                f.write("\n\n")

    print(f'\n💾 保存完了！')
    print(f'📄 ファイル: {filepath}')
    return filepath

# ================================================================
# 🚀 メイン実行
# ================================================================

print(f'🛍️  DMMから商品情報を取得中（フロア: {DMM_FLOOR} / モード: {DMM_SORT_MODE}）...')

all_sections = []

for sort_key, sort_label in SORT_LIST:
    raw_items = fetch_dmm_products(sort_key, sort_label)
    if not raw_items:
        print(f'  ⚠️  [{sort_label}] 商品が取得できませんでした。スキップします。')
        continue

    products = [parse_product(item) for item in raw_items]

    if PRICE_RANGE_BOUNDS:
        before_count = len(products)
        products = [p for p in products if price_in_range(p)]
        print(f'  💰 価格フィルター適用: {before_count}件 → {len(products)}件')

    if not products:
        print(f'  ⚠️  [{sort_label}] 価格条件に合う商品がありませんでした。スキップします。')
        continue

    print(f'  📝 [{sort_label}] 投稿文を生成中...')

    posts = []
    for p in products:
        text = build_x_post(p)
        posts.append((p, text))
        print(f"    ✅ [{len(text)}文字] {p['title'][:30]}...")

    all_sections.append((sort_label, posts))

if not all_sections:
    print('❌ 商品が1件も取得できませんでした。')
    sys.exit(1)

first_label, first_posts = all_sections[0]
print('\n' + '=' * 60)
print(f'📋 投稿文プレビュー（{first_label} 1件目）')
print('=' * 60)
print(first_posts[0][1])
print('=' * 60)

save_posts(all_sections)

total = sum(len(p) for _, p in all_sections)
print(f'\n✅ 完了！合計 {total} 件の投稿文を保存しました。')
print('テキストファイルを開いてXに手動投稿してください。')
