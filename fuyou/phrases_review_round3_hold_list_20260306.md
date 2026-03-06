# phrases_eo_en_ja_zh_ko_ru_fulfilled_251130.csv

未修正・据え置き理由一覧
4周目反映版

更新日: 2026-03-06

対象ファイル:
- `phrases_eo_en_ja_zh_ko_ru_fulfilled_251130.csv`
- `phrases_eo_en_ja_zh_ko_ru_fulfilled_251130 copy.csv`

一致確認:
- `cmp_exit=0`
- `md5=13dad84c26a36519e0313fad4c96dc77`

判定基準:
- RU は最重要参考列
- 実運用では Esperanto と JA/ZH/KO の対応を重視
- 文脈別許容は残す
- 意味のズレが明確な箇所だけ修正
- PIV / Glosbe で裏取りできない置換はしない
- 「辞書にない」だけでは直さない
- 複合語として透明で、意味ズレもないものは原則据え置く

## 1. この文書の見方

この文書では、未修正語を次の2群に分ける。

- `保留継続`: 4周目終了時点でも、まだ少し気になる点が残っている語群
- `保留から外した語`: 以前は保留候補だったが、4周目までの確認で現形維持でよいと判断した語群

実務上、次に重点再調査すべきなのは `保留継続` だけでよい。

## 2. 保留継続

件数:
- `19語群 / 25 PhraseID`

### 2.1 高優先

意味の焦点や語義の取り方にまだ少し緊張があるもの。

| 優先 | PhraseID | 現行文 | 気になる点 | 据え置き理由 |
|---|---:|---|---|---|
| 高 | 902 | Mi estas ĉi tie por labori | RU は「出張」寄り | JA/ZH/KO/EN は「仕事で来ている」と一致しており、RU に寄せて動かすのは危険 |
| 高 | 1560 | Mi estas merkatika administranto | `marketing manager / specialist` の揺れ | 列間の意味を固定した安全な置換先を確定できない |
| 高 | 1590 | Ŝi estas en patrina forpermeso | 語の標準性 | 用例は見えるが、さらに安全な標準形への置換根拠が足りない |
| 高 | 1591 | Li estas en patra forpermeso | 語の標準性 | 上と同じ |
| 高 | 1906 | Kie mi povas preni la navedbuson? | `navedbuso` が弱め | より安全な置換先を辞書根拠付きで確定できない |

### 2.2 中優先

見出し語としては弱めだが、文脈上は十分通るもの。

| 優先 | PhraseID | 現行文 | 気になる点 | 据え置き理由 |
|---|---:|---|---|---|
| 中 | 1664 | Mi ofte faras laborvojaĝojn | 見出し語として弱め | 意味は明確で、RU/JA/ZH/KO とも整合 |
| 中 | 2047 | Mi havas du manbagaĝojn | `manbagaĝo` が弱め | 空港文脈では十分自然 |
| 中 | 2048 | Vi havas tro da manbagaĝo | `manbagaĝo` が弱め | 上と同じ |
| 中 | 2055 | Ĉu mi povus vidi vian manbagaĝon, mi petas? | `manbagaĝo` が弱め | 上と同じ |
| 中 | 2056 | Mi havas unu manbagaĝon | `manbagaĝo` が弱め | 上と同じ |
| 中 | 2058 | Ĝi estas tro granda por manbagaĝo | `manbagaĝo` が弱め | 上と同じ |
| 中 | 2623 | Ĉu vi havas rulseĝan aliron? | やや説明的 | より安全な標準置換を確定できない |

### 2.3 低優先

主に透明な複合語、硬さ、または表記揺れの問題。現状維持でも実害は小さい。

| 優先 | PhraseID | 現行文 | 気になる点 | 据え置き理由 |
|---|---:|---|---|---|
| 低 | 456 | Parolu kun mi en la mandarena ĉina lingvo | やや硬い | 誤りと断定する根拠不足 |
| 低 | 1253 | Ni forveturu de ĉi tie | 直訳感 | 意味ズレは明確でない |
| 低 | 1454 | Kiu estas la templimo por paroladoj? | 複合語の自然さ | 生産的複合語として成立しうる |
| 低 | 2149 | Bonvolu remeti vian seĝodorson en la vertikalan pozicion | 複合語の自然さ | 意味は明瞭で、壊す理由がない |
| 低 | 2181 | Bagaĝa elpreno | 透明複合語 | 意味は明確、置換先確定不足 |
| 低 | 2213 | Ĉu ĉi tiu aŭto havas infanserurojn? | 透明複合語 | 意味は明確、置換先確定不足 |
| 低 | 2225 | Kiom longa estas la minimuma luoperiodo? | 透明複合語 | 上と同じ |
| 低 | 2254 | Ĉu vi havas vojmapon? | 透明複合語 | 上と同じ |
| 低 | 2278 | Kiom malproksimas la sekva serva areo? | やや calque 的 | 意味ズレは明確でない |
| 低 | 2292 | Mi staris en trafikblokiĝo dum unu horo | 透明複合語 | 意味は明確、壊す理由がない |
| 低 | 2782 | Ĉu la servkotizo estas inkluzivita? | 表記揺れ | `servkotizo / servokotizo` の両形に実ページあり |
| 低 | 2783 | Servokotizo ne estas inkluzivita | 表記揺れ | 上と同じ |
| 低 | 2796 | Kiom estas la servokotizo kaj la imposto? | 表記揺れ | 上と同じ |

## 3. 保留から外した語

以下は以前は弱候補だったが、4周目までの確認で「現形維持でよい」と判断した語群。
次回以降は、原則として重点再調査対象から外してよい。

### 3.1 4周目で据え置き確定に寄った語

- `mandarena`
- `picejo`
- `klubumi`
- `dombestoj`
- `fantombildo`
- `bandaĝo`
- `vojaĝkostoj`
- `solvanto`
- `interreta kafejo`
- `aŭtobushaltejo`
- `enŝipiĝo`
- `biletaŭtomatoj`
- `vojaĝkarto`
- `abonbileto`
- `pakaĵujo`
- `restmono`
- `taksihaltejo`
- `bankaŭtomato`
- `monŝranko`
- `gimnastikejo`

### 3.2 ホテル・旅行

- `elregistriĝi`
- `longdaŭra restado`
- `telefona ŝargilo`
- `ventuzilo`
- `halala`
- `kalcono`

### 3.3 飲食・買い物

- `naĉoj`
- `barela biero`
- `bekono`
- `ringokukoj`
- `fingrosandaloj`
- `vizaĝpudro`
- `skribmaterialoj`
- `laktoskuaĵo`

### 3.4 娯楽・スポーツ

- `antikvaran librovendejon`
- `drama teatro`
- `karikatursalono`
- `surfotabulo`
- `aerbotelo`
- `tendumejo`

### 3.5 銀行・美容・健康

- `monretiro`
- `kontoekstrakto`
- `duamana`
- `frizaĵo`
- `feni`
- `skalpo`
- `malsanasekuro`
- `malsanatestilo`
- `dentpurigado`
- `okulvitrujo`

### 3.6 電話・郵便

- `telefonkarto`
- `retelefoni`
- `aŭtomata respondilo`
- `afranko`
- `giĉeto`
- `poŝtrestante`
- `aldonaĵo`

## 4. 実務判断

- 次に本当に重点再調査すべきなのは `保留継続 19語群` のみ
- その中でも、先に見る価値があるのは `高優先 5語群`
- `servkotizo / servokotizo` は誤りというより表記揺れとして扱うのが妥当
- `保留から外した語` は、現時点では未修正のままで閉じてよい

## 5. 参照

主に以下を確認に使用:

- PIV
  - https://vortaro.net/
- Glosbe
  - https://glosbe.com/

## 6. 5周目結果

実施日:
- 2026-03-06

対象:
- `ID156〜1255` は通しで再点検
- `ID1256〜5155` は、前周までの `保留継続`・弱候補を重点的に再検証

結果:
- **追加修正なし**
- `cmp_exit=0`
- `md5=13dad84c26a36519e0313fad4c96dc77`

### 6.1 5周目で確認したこと

- `ID456` `mandarena ĉina lingvo`
- `ID767` `surmeti bandaĝon`
- `ID826` `fari lian fantombildon`
- `ID902` `Mi estas ĉi tie por labori`
- `ID1064` `Mi amas klubumi`
- `ID1092` `Ĉu vi havas dombestojn?`
- `ID1253` `Ni forveturu de ĉi tie`
- `ID1350` `Estas pli bone ol la lastan fojon`
- `ID1454` `templimo`
- `ID1560` `merkatika administranto`
- `ID1590` `patrina forpermeso`
- `ID1591` `patra forpermeso`
- `ID1664` `laborvojaĝojn`
- `ID1906` `navedbuso`
- `ID2047/2048/2055/2056/2058` `manbagaĝo`
- `ID2149` `seĝodorso`
- `ID2181` `bagaĝa elpreno`
- `ID2213` `infanseruroj`
- `ID2225` `luoperiodo`
- `ID2254` `vojmapo`
- `ID2278` `serva areo`
- `ID2292` `trafikblokiĝo`
- `ID2782/2783/2796` `servkotizo / servokotizo`

### 6.2 5周目で据え置き判断がさらに強くなった語

以下は、5周目で外部用例・辞書側の裏付けが相対的に増え、少なくとも「AI造語だから直すべき」とは言えないことが、前より明確になった語。

- `laborvojaĝo`
- `patrina forpermeso`
- `patra forpermeso`
- `manbagaĝo`
- `seĝodorso`

### 6.3 5周目終了時点の実務判断

- `保留継続` 群についても、5周目で**新たに動かすだけの根拠は出なかった**
- したがって、CSV 本体はこの時点でも**据え置きが妥当**
- 次に再調査する場合も、まずは `高優先 5語群` だけを対象にすれば十分

### 6.4 5周目で確認した補助ソース

- `laborvojaĝo`
  - https://www.esperanto-panorama.net/vortaro/labvoja.htm
- `patrina forpermeso`
  - https://majstro.com/ser/e2e?q=patrina%20forpermeso
- `patra forpermeso`
  - https://majstro.com/ser/e2e?q=patra%20forpermeso
- `manbagaĝo`
  - https://www.esperanto-panorama.net/vortaro/manbagag.htm
