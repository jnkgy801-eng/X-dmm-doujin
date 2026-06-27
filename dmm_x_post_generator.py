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
        "ニヤニヤが止まらない展開で、深夜に読み始めたら止まれなくなった😂",
        "このドキドキ感、ラブコメ好きにはわかってもらえると思う💕",
        "設定が好みすぎてズルい。こういうの待ってた",
    ],
    '巨乳': [
        "ボリューム感とキャラの可愛さが両立してる作品、意外と少ない",
        "絵柄がツボすぎた。これ系好きな人には素直におすすめしたい",
        "こういう作品、定期的に出てきてほしいと思う派です",
    ],
    '人妻・主婦': [
        "こういう背徳感のある設定、なかなか抜け出せないんだよな😅",
        "人妻もので外れ引いたことほぼないけど、これも安定してた",
        "禁断感の演出がうまくて、読み終わった後に罪悪感ある系😇",
    ],
    '制服': [
        "学園ものは設定の作り込みで全然変わるけど、これはちゃんとしてる",
        "このジャンルの安定感ってあるよね。今回も期待を裏切らなかった",
        "制服好きにはそのまま刺さる構成です✏️",
    ],
    '熟女': [
        "大人の色気って絵力が要るけど、これはそこをちゃんとクリアしてる",
        "熟女ものでこの完成度は普通に高いと思う",
        "このジャンル好きな人なら間違いなく刺さる作品です",
    ],
    '近親相姦': [
        "タブー設定が好きな人には刺さる構成。引きが強くて一気読みした",
        "こういう禁断系、設定だけじゃなくてストーリーもちゃんとしてる",
        "後味がクセになる系だった…🌙",
    ],
    '寝取り・寝取られ・NTR': [
        "NTR好きにはわかる、この「見てはいけないのに見てしまう」感覚",
        "メンタルにくる系が好きな人に刺さる内容です👁",
        "NTR耐性ある人なら最後まで引き込まれると思う",
    ],
    '調教': [
        "展開の流れが読んでてテンション上がる構成だった🔥",
        "このジャンルって進行の緩急が大事だと思うけど、これはうまい",
        "こういう一作、定期的に読みたくなる系です",
    ],
    '中出し': [
        "内容の密度がしっかりある作品。薄いやつとは違う",
        "このジャンルでこの完成度は、素直に良かったと言える",
        "描写の丁寧さが好きだった。雑なの多い中でこれは当たりだと思う",
    ],
    '異種姦': [
        "ファンタジー設定が好きな人は世界観から楽しめると思う🐉",
        "異種姦ものって世界観の作り込みで全然変わるけど、これは好きな部類",
        "設定の独自性があって、読んでて飽きなかった",
    ],
    'VR': [
        "VRで見るとこれが一番没入感あると思う。画質の差が出る作品",
        "VR専用に作られてる感がちゃんとあって、臨場感が違う",
        "8K対応なら画質の差を体感できる。VR持ちには普通におすすめ",
    ],
    '4時間以上作品': [
        "ボリューム系が好きな人には満足度が高い一本だと思う",
        "長尺作品でハズレ引きたくない人に向いてる内容です",
        "コスパ重視で探してる人に刺さる作品",
    ],
}

COPY_TEMPLATES_FALLBACK = [
    "タイトルで気になった人は、とりあえず詳細だけ覗いてみて",
    "深夜にひっそり楽しむやつ、これです🌙",
    "このジャンル好きな人には刺さると思う",
    "こういうの待ってた人、いるんじゃないかな",
    "見てみたら予想より良かった系の作品",
    "タイトルの雰囲気通りの内容で、期待は裏切らない",
    "このジャンルが好きなら後悔しない内容だと思う",
    "説明より作品ページ見た方が早い。気になるなら覗いてみて",
    "深夜のお供にちょうどいい密度感です🌙",
    "興味あるなら損はしない一作だと思う",
]


def get_copy_ai(title: str, genres: list, maker: str, price: str) -> str:
    """Claude APIを使ってタイトル・ジャンルに合った自然な複数行コメントを生成する。
    API失敗時はフォールバックテンプレートを返す。"""
    if not ANTHROPIC_API_KEY:
        return _get_copy_fallback(genres)

    genre_str = '・'.join(genres) if genres else 'なし'
    maker_str = maker if maker else '不明'
    price_str = price if price else '不明'

    if DMM_FLOOR == 'doujin':
        floor_label = '同人誌・同人CG集'
        no_sample_note = '- 「サンプルを見て」「試し読み」などサンプル動画・試読を促す表現は使わない（同人作品のため）\n'
    else:
        floor_label = 'AV・動画'
        no_sample_note = ''

    prompt = (
        f"{floor_label}のX(Twitter)アフィリエイト投稿の「紹介本文」を作ってください。\n\n"
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
        f"{no_sample_note}"
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

    # レビュー情報
    review_info = item.get('review', {}) or {}
    try:
        review_avg   = float(review_info.get('average', 0) or 0)
        review_count = int(review_info.get('count', 0) or 0)
    except (ValueError, TypeError):
        review_avg   = 0.0
        review_count = 0
    review_avg   = round(review_avg, 2) if review_avg else None
    review_count = review_count if review_count else None

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
        'review_avg':       review_avg,
        'review_count':     review_count,
    }

def clean_url(url):
    if not url:
        return ''
    url = url.strip().replace('\n', '').replace('\r', '').replace('　', '')
    if not url.startswith('http'):
        return ''
    return url


def shorten_url(url):
    """TinyURLでURLを短縮する。失敗時は元のURLをそのまま返す。"""
    if not url:
        return url
    try:
        resp = requests.get(
            'https://tinyurl.com/api-create.php',
            params={'url': url},
            timeout=8,
        )
        if resp.status_code == 200 and resp.text.startswith('http'):
            return resp.text.strip()
    except Exception as e:
        print(f'    ⚠️  URL短縮に失敗（元のURLを使用）: {e}')
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
    """ポスト1（紹介）とポスト2（詳細+URL）の2本構成でスレッドテキストを返す。"""
    hashtags     = HASHTAG_MAP.get(DMM_FLOOR, HASHTAG_MAP['default'])
    raw_url      = clean_url(product['affiliate_url'])
    short_url    = shorten_url(raw_url)
    act_tags     = actor_tags(product['actors'])
    copy         = get_copy_ai(product['title'], product['genres'], product.get('maker', ''), product['price'])

    title        = product['title']
    review_avg   = product.get('review_avg')
    review_count = product.get('review_count')

    # ── レビュー文字列 ────────────────────────────────────────────
    review_str = ''
    if review_avg and review_count and review_count >= 5:
        review_str = f'レビュー平均{review_avg}（{review_count}件）の高評価'

    # ── ポスト2（詳細情報＋URL）────────────────────────────────────
    def build_post2(genre_limit):
        lines = ['📌 気に入ったら本編はこちら👇']
        # 購入後押し（レビューがあればレビュー、なければシンプルな一言）
        if review_str or product.get('maker'):
            reason_parts = []
            if review_str:
                reason_parts.append(review_str)
            if product.get('maker'):
                reason_parts.append(f"{product['maker']}制作")
            # doujinはサンプル動画なし → 「作品ページを見てみて」に変える
            cta = '作品ページを見てみて' if DMM_FLOOR == 'doujin' else 'サンプルだけでも見てみて'
            lines.append('、'.join(reason_parts) + 'の作品。気になるなら' + cta)
        # 価格
        if product['price']:
            lines.append(f'💰 {product["price"]}')
        # ジャンルタグ
        if product['genres']:
            lines.append(f'🏷 {genre_tags(product["genres"][:genre_limit])}')
        lines.append(short_url)
        lines.append(hashtags)
        return '\n'.join(lines)

    post2 = build_post2(genre_limit=3)
    if len(post2) > 280:
        post2 = build_post2(genre_limit=1)

    # ── ポスト1（タイトル＋コメント＋URL）────────────────────────
    def build_post1(display_title):
        lines = [
            f'📖 {display_title}',
            '',
            copy,
            short_url,
        ]
        if act_tags:
            lines.insert(-1, f'👤 {act_tags}')
        return '\n'.join(lines)

    post1 = build_post1(title)
    if len(post1) > 280:
        short_title = title[:38] + '…' if len(title) > 38 else title
        post1 = build_post1(short_title)
    if len(post1) > 280:
        # 出演者タグを外してもオーバーなら本文だけにする
        post1 = f'📖 {title[:38]}…\n\n{copy}\n{short_url}'

    return post1, post2

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

            for i, (product, thread) in enumerate(posts, 1):
                post1, post2 = thread
                f.write(f"--- {sort_label} {i}/{len(posts)} ---\n")
                f.write(f"商品名: {product['title']}\n")
                f.write(f"文字数: ポスト1={len(post1)}文字 / ポスト2={len(post2)}文字\n")
                f.write(f"URL確認: {product['affiliate_url']}\n")
                if product.get('sample_movie_url'):
                    f.write(f"サンプル動画: {product['sample_movie_url']}\n")
                f.write("-" * 40 + "\n")
                f.write("【ポスト1】\n")
                f.write(post1)
                f.write("\n\n【ポスト2（スレッド続き）】\n")
                f.write(post2)
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
        post1, post2 = build_x_post(p)
        posts.append((p, (post1, post2)))
        print(f"    ✅ [ポスト1: {len(post1)}文字 / ポスト2: {len(post2)}文字] {p['title'][:30]}...")

    all_sections.append((sort_label, posts))

if not all_sections:
    print('❌ 商品が1件も取得できませんでした。')
    sys.exit(1)

first_label, first_posts = all_sections[0]
print('\n' + '=' * 60)
print(f'📋 投稿文プレビュー（{first_label} 1件目）')
print('=' * 60)
print('【ポスト1】')
print(first_posts[0][1][0])
print('\n【ポスト2（スレッド続き）】')
print(first_posts[0][1][1])
print('=' * 60)

save_posts(all_sections)

total = sum(len(p) for _, p in all_sections)
print(f'\n✅ 完了！合計 {total} 件の投稿文を保存しました。')
print('テキストファイルを開いてXに手動投稿してください。')
