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
# 🤖 AI動的コピー生成（購買意欲を高める2行構成）
# ================================================================

ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY', '')

# AI生成が使えない場合のフォールバック用ジャンル別テンプレート
# （1行目：共感・2行目：購買背中押し の2行構成）
COPY_TEMPLATES_BY_GENRE = {
    'ラブコメ': [
        "この設定、好きな人には刺さりすぎる内容だった💕\nラブコメ好きなら後悔しない一作です",
        "ニヤニヤが止まらない展開で深夜に読み始めたら止まれなかった\nレビューも高評価多数で安定感あり",
    ],
    '巨乳': [
        "ボリューム感とキャラの可愛さが両立してる、意外と少ないタイプ\nこのジャンル好きなら試す価値あり",
        "絵柄がツボすぎた。これ系好きな人には素直におすすめしたい\n価格も手が出しやすい範囲",
    ],
    '人妻・主婦': [
        "こういう背徳感のある設定、なかなか抜け出せないんだよな😅\n人妻もので外れ引いたことほぼない、これも安定してた",
        "禁断感の演出がうまくて読み終わった後に罪悪感ある系😇\nレビュー評価も高く、買って損はない",
    ],
    '制服': [
        "学園ものは設定の作り込みで全然変わるけど、これはちゃんとしてる\n制服好きにはそのまま刺さる構成です✏️",
        "このジャンルの安定感ってあるよね。今回も期待を裏切らなかった\n迷ってるなら詳細ページで確認してみて",
    ],
    '熟女': [
        "大人の色気って絵力が要るけど、これはそこをちゃんとクリアしてる\n熟女もので完成度高いのは貴重、おすすめです",
        "このジャンル好きな人なら間違いなく刺さる作品です\n高評価レビューが多く、信頼できる一本",
    ],
    '近親相姦': [
        "タブー設定が好きな人には刺さる構成。引きが強くて一気読みした\n後味がクセになる系、詳細で確認してみて",
    ],
    '寝取り・寝取られ・NTR': [
        "NTR好きにはわかる、この「見てはいけないのに見てしまう」感覚\nNTR耐性ある人なら最後まで引き込まれると思う",
    ],
    '調教': [
        "展開の流れが読んでてテンション上がる構成だった🔥\n進行の緩急がうまい。このジャンル好きなら損しない",
    ],
    '中出し': [
        "内容の密度がしっかりある作品。薄いやつとは違う\nこのジャンルでこの完成度は当たりだと思う",
    ],
    '異種姦': [
        "ファンタジー設定が好きな人は世界観から楽しめると思う🐉\n設定の独自性があって、これは好きな部類",
    ],
    'VR': [
        "VR専用に作られてる感がちゃんとあって、臨場感が違う\n8K対応なら画質の差を体感できる。VR持ちには普通におすすめ",
    ],
    '4時間以上作品': [
        "ボリューム系が好きな人には満足度が高い一本だと思う\nコスパ重視で探してる人に刺さる作品",
    ],
}

COPY_TEMPLATES_FALLBACK = [
    "このジャンル好きな人には刺さると思う\n詳細ページで確認してから決めてみて",
    "深夜のお供にちょうどいい密度感🌙\nレビュー評価も高く、選んで損はない",
    "タイトルの雰囲気通りの内容で、期待は裏切らない\n気になるなら詳細だけでも覗いてみて",
    "こういうの待ってた人、いるんじゃないかな\n価格と内容のバランスが良い作品です",
    "説明より作品ページ見た方が早い\n興味あるなら損はしない一作だと思う",
]


def get_copy_ai(title: str, genres: list, maker: str, price: str, review_avg, review_count) -> str:
    """Claude APIを使って購買意欲を高める2行コメントを生成する。
    API失敗時はフォールバックテンプレートを返す。"""
    if not ANTHROPIC_API_KEY:
        return _get_copy_fallback(genres)

    genre_str = '・'.join(genres) if genres else 'なし'
    maker_str = maker if maker else '不明'
    price_str = price if price else '不明'

    # レビュー情報を文字列化
    review_str = ''
    if review_avg and review_count and review_count >= 5:
        review_str = f'平均{review_avg}点（{review_count}件）'

    if DMM_FLOOR == 'doujin':
        floor_label = '同人誌・同人CG集'
        no_sample_note = '- 「サンプルを見て」「試し読み」などサンプル動画・試読を促す表現は使わない（同人作品のため）\n'
        cta_note = '- 2行目はジャンルが好きな人に「買う価値がある」と感じさせる理由を一言で\n'
    else:
        floor_label = 'AV・動画'
        no_sample_note = ''
        cta_note = '- 2行目は「レビュー評価」「価格」「サンプルで確認を」のうち自然に使えるものを選んで購入の背中を押す\n'

    prompt = (
        f"{floor_label}のX(Twitter)アフィリエイト投稿の「紹介本文」を作ってください。\n\n"
        f"作品タイトル：{title}\n"
        f"ジャンル：{genre_str}\n"
        f"サークル/メーカー：{maker_str}\n"
        f"価格：{price_str}\n"
        f"レビュー：{review_str if review_str else 'なし'}\n\n"
        f"【条件】\n"
        f"- 必ず2行構成、合計で50〜80文字（改行込み）\n"
        f"- 1行目（25〜40文字）：ジャンルや設定への共感・反応。そのジャンルが好きな人が普通につぶやくような自然な口語体\n"
        f"- 2行目（25〜40文字）：今すぐ見たい・買いたいと思わせる具体的な理由。レビュー件数や評価点があれば積極的に使う\n"
        f"{cta_note}"
        f"- AIっぽい宣伝文句（「話題沸騰中」「クオリティに驚く」「ファン必見」「期間限定」等）は絶対使わない\n"
        f"- 絵文字は全体で0〜2個まで。「！」「✨」の多用NG\n"
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
        if text and len(text) <= 100:
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
    """ジャンル名をハッシュタグ形式に変換する。"""
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


# ================================================================
# ✂️  文字数カウント（Xの仕様: URLは23文字固定扱い）
# ================================================================

URL_CHAR_COUNT = 23  # XはURLを常に23文字としてカウント

def x_len(text: str) -> int:
    """Xの文字数カウントルールに準拠した文字数を返す。
    URLはhttps://またはhttp://で始まる文字列を23文字として計算。"""
    import re
    url_pattern = re.compile(r'https?://\S+')
    count = 0
    last_end = 0
    for m in url_pattern.finditer(text):
        count += len(text[last_end:m.start()])
        count += URL_CHAR_COUNT
        last_end = m.end()
    count += len(text[last_end:])
    return count


X_LIMIT = 280  # Xの投稿上限文字数


def build_x_post(product):
    """ポスト1（紹介）とポスト2（詳細+URL）の2本構成でスレッドテキストを返す。
    両ポストともXの280文字制限を超えないように自動調整する。"""
    hashtags  = HASHTAG_MAP.get(DMM_FLOOR, HASHTAG_MAP['default'])
    raw_url   = clean_url(product['affiliate_url'])
    short_url = shorten_url(raw_url)
    act_tags  = actor_tags(product['actors'])
    copy      = get_copy_ai(
        product['title'],
        product['genres'],
        product.get('maker', ''),
        product['price'],
        product.get('review_avg'),
        product.get('review_count'),
    )

    title        = product['title']
    review_avg   = product.get('review_avg')
    review_count = product.get('review_count')

    # ── レビュー・メーカー文字列 ─────────────────────────────────
    reason_parts = []
    if review_avg and review_count and review_count >= 5:
        reason_parts.append(f'レビュー平均{review_avg}（{review_count}件）')
    if product.get('maker'):
        reason_parts.append(f"{product['maker']}制作")

    if DMM_FLOOR == 'doujin':
        cta = '作品ページを確認してみて'
    else:
        if review_count and review_count >= 20:
            cta = 'サンプルで確認してから決めて'
        elif product.get('price_num') and product['price_num'] <= 1000:
            cta = 'この価格なら試す価値あり'
        else:
            cta = 'サンプルだけでも見てみて'

    # ── ポスト2（詳細情報＋URL）────────────────────────────────────
    def build_post2(genre_limit):
        lines = ['📌 気に入ったら本編はこちら👇']
        if reason_parts:
            lines.append('、'.join(reason_parts) + 'の作品。' + cta)
        if product['price']:
            lines.append(f'💰 {product["price"]}')
        if product['genres'] and genre_limit > 0:
            lines.append(f'🏷 {genre_tags(product["genres"][:genre_limit])}')
        lines.append(short_url)
        lines.append(hashtags)
        return '\n'.join(lines)

    post2 = build_post2(genre_limit=3)
    if x_len(post2) > X_LIMIT:
        post2 = build_post2(genre_limit=1)
    if x_len(post2) > X_LIMIT:
        post2 = build_post2(genre_limit=0)

    # ── ポスト1（タイトル＋コピー＋URL）────────────────────────────
    def build_post1(display_title, include_actor):
        lines = [f'📖 {display_title}', '', copy, short_url]
        if include_actor and act_tags:
            lines.insert(-1, f'👤 {act_tags}')
        return '\n'.join(lines)

    # タイトル長を段階的に縮めて280字以内に収める
    def truncate_title(max_len):
        if len(title) > max_len:
            return title[:max_len] + '…'
        return title

    post1 = build_post1(title, include_actor=True)
    if x_len(post1) > X_LIMIT:
        post1 = build_post1(title, include_actor=False)
    if x_len(post1) > X_LIMIT:
        post1 = build_post1(truncate_title(40), include_actor=False)
    if x_len(post1) > X_LIMIT:
        post1 = build_post1(truncate_title(20), include_actor=False)

    # それでも超える場合はコピーを1行目だけに切り詰める
    if x_len(post1) > X_LIMIT:
        copy_line1 = copy.split('\n')[0]
        post1 = f'📖 {truncate_title(20)}\n\n{copy_line1}\n{short_url}'

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
    explicit = os.environ.get('SAVE_DIR', '').strip()
    if explicit:
        Path(explicit).mkdir(parents=True, exist_ok=True)
        return explicit

    if os.environ.get('SAVE_TO_REPO', '').lower() == 'true':
        out = Path('outputs')
        out.mkdir(exist_ok=True)
        return str(out)

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
                p1_xlen = x_len(post1)
                p2_xlen = x_len(post2)
                over1 = ' ⚠️ 超過' if p1_xlen > X_LIMIT else ''
                over2 = ' ⚠️ 超過' if p2_xlen > X_LIMIT else ''
                f.write(f"--- {sort_label} {i}/{len(posts)} ---\n")
                f.write(f"商品名: {product['title']}\n")
                f.write(f"文字数(X換算): ポスト1={p1_xlen}文字{over1} / ポスト2={p2_xlen}文字{over2}\n")
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
        p1_xlen = x_len(post1)
        p2_xlen = x_len(post2)
        warn = ' ⚠️ 超過あり' if p1_xlen > X_LIMIT or p2_xlen > X_LIMIT else ''
        posts.append((p, (post1, post2)))
        print(f"    ✅ [P1:{p1_xlen}字 / P2:{p2_xlen}字{warn}] {p['title'][:30]}...")

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
