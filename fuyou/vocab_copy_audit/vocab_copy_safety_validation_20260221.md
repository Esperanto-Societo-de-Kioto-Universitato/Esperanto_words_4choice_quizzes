# Safe Validation Report (2026-02-21)

対象:
- `2890 Gravaj Esperantaj Vortoj kun Signifoj en la Japana, Ĉina kaj Korea_251129_plajnova copy.csv`
- 基準: `2890 Gravaj Esperantaj Vortoj kun Signifoj en la Japana, Ĉina kaj Korea_251129_plajnova.csv`
- バックアップ1（safe-fix前）: `2890 Gravaj Esperantaj Vortoj kun Signifoj en la Japana, Ĉina kaj Korea_251129_plajnova copy.before_safe_fix_20260221.csv`
- バックアップ2（optional3前）: `2890 Gravaj Esperantaj Vortoj kun Signifoj en la Japana, Ĉina kaj Korea_251129_plajnova copy.before_optional3_fix_20260221.csv`
- バックアップ3（round2高確度1件前）: `2890 Gravaj Esperantaj Vortoj kun Signifoj en la Japana, Ĉina kaj Korea_251129_plajnova copy.before_round2_teraso_fix_20260221.csv`
- バックアップ4（round3低優先前）: `2890 Gravaj Esperantaj Vortoj kun Signifoj en la Japana, Ĉina kaj Korea_251129_plajnova copy.before_round3_low_fix_20260221.csv`

## Change Scope Check
- vs baseline original
  - diff cells: `159`
  - diff by column: `{'Korean_Trans': 70, 'Chinese_Trans': 34, 'Japanese_Trans': 55}`
- vs before_safe_fix
  - diff cells: `87`
  - diff by column: `{'Korean_Trans': 28, 'Japanese_Trans': 55, 'Chinese_Trans': 4}`
- vs before_optional3_fix
  - diff cells: `47`
  - diff by column: `{'Korean_Trans': 28, 'Japanese_Trans': 16, 'Chinese_Trans': 3}`
- vs before_round2_teraso_fix
  - diff cells: `44`
  - diff by column: `{'Korean_Trans': 27, 'Japanese_Trans': 16, 'Chinese_Trans': 1}`
- vs before_round3_low_fix
  - diff cells: `43`
  - diff by column: `{'Korean_Trans': 27, 'Japanese_Trans': 16}`

## Applied in order
1. safe-fix: JA重複括弧55 + palto(ZH)1
2. optional3: super(ZH), ŝelo(ZH), ĝiri(KO)
3. round2-high: teraso(ZH) 地坛 -> 台地
4. round3-low: style_spacing 27 + style_redundant_gloss 16

## SHA-256
- `b8ce168b5822d87facafaae309332287e8d38890a03692215ef120b7ac310b09`  `2890 Gravaj Esperantaj Vortoj kun Signifoj en la Japana, Ĉina kaj Korea_251129_plajnova copy.csv`
- `daad9a6fc06840ced14e92251b8e06198b47a4393cb1610e91924bab83168ac8`  `2890 Gravaj Esperantaj Vortoj kun Signifoj en la Japana, Ĉina kaj Korea_251129_plajnova.csv`
- `755816085fc89de7dd61655f48bd705fc5d9d95c6a02ac991fcca3cdbb4e914a`  `2890 Gravaj Esperantaj Vortoj kun Signifoj en la Japana, Ĉina kaj Korea_251129_plajnova copy.before_safe_fix_20260221.csv`
- `55479b93ae6bed6b335c1e16b8e81e75daab567b2e2ab7b9d8b2ae0fe8b98671`  `2890 Gravaj Esperantaj Vortoj kun Signifoj en la Japana, Ĉina kaj Korea_251129_plajnova copy.before_optional3_fix_20260221.csv`
- `8f1ee4ecf425acde8e934c800f832add9265f4b425c1786f6aa03d812d4819e4`  `2890 Gravaj Esperantaj Vortoj kun Signifoj en la Japana, Ĉina kaj Korea_251129_plajnova copy.before_round2_teraso_fix_20260221.csv`
- `bf843939d75766e2d090ce0195a5433032509d350b7b8da390fca784c17b9fb0`  `2890 Gravaj Esperantaj Vortoj kun Signifoj en la Japana, Ĉina kaj Korea_251129_plajnova copy.before_round3_low_fix_20260221.csv`
