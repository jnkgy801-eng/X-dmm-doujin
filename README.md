name: DMMアフィリエイト Instagram 自動投稿

on:
  schedule:
    # UTC時間で4時間ごとに実行
    # 0時・4時・8時・12時・16時・20時（UTC）= 9時・13時・17時・21時・1時・5時（JST）
    - cron: '0 0,4,8,12,16,20 * * *'

  # 手動実行ボタン（テスト用）
  workflow_dispatch:
    inputs:
      post_index:
        description: '投稿する商品番号（0始まり）'
        required: false
        default: '0'
      post_all:
        description: '全件投稿する場合は true'
        required: false
        default: 'false'
      dmm_floor:
        description: 'DMMフロア（digital / mono / anime / book）'
        required: false
        default: 'digital'
      dmm_sort:
        description: 'ソート順（-date / rank / -price）'
        required: false
        default: '-date'

jobs:
  post:
    runs-on: ubuntu-latest
    timeout-minutes: 15

    steps:
      - name: リポジトリをチェックアウト
        uses: actions/checkout@v4

      - name: Python 3.11 をセットアップ
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: 依存ライブラリをインストール
        run: |
          pip install requests pillow

      - name: DMMアフィリエイト Instagram 自動投稿を実行
        env:
          META_ACCESS_TOKEN:    ${{ secrets.META_ACCESS_TOKEN }}
          INSTAGRAM_ACCOUNT_ID: ${{ secrets.INSTAGRAM_ACCOUNT_ID }}
          IMGBB_API_KEY:        ${{ secrets.IMGBB_API_KEY }}
          DMM_API_ID:           ${{ secrets.DMM_API_ID }}
          DMM_AFFILIATE_ID:     ${{ secrets.DMM_AFFILIATE_ID }}
          POST_INDEX:  ${{ github.event.inputs.post_index  || '0' }}
          POST_ALL:    ${{ github.event.inputs.post_all    || 'false' }}
          DMM_FLOOR:   ${{ github.event.inputs.dmm_floor   || 'digital' }}
          DMM_SORT:    ${{ github.event.inputs.dmm_sort    || '-date' }}
        run: python main.py
