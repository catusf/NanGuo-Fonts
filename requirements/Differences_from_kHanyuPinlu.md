# Differences from kHanyuPinlu

Comparison of [`sources/data/kHanyuPinlu.txt`](../sources/data/kHanyuPinlu.txt)
(Unicode Han Database frequency-ordered readings, 3,799 entries) against
the project's primary-reading data.

At time of comparison, primary readings lived in two places:

- `sources/data/pinyin_map.json` — a stale derived cache (since deleted)
- `sources/data/heteronym_map.json` — the live source the build script reads
  (slot 0 of each 6-slot array is the primary reading)

## Summary

| Metric | Count |
|---|---|
| kHanyuPinlu entries | 3,799 |
| Primary reading differed from (now-deleted) `pinyin_map.json` | 162 |
| Heteronym set differed from `heteronym_map.json` | 365 |
| In kHanyuPinlu only (likely traditional / out-of-GB2312) | 970 |
| In `pinyin_map.json` only (low-frequency, no Unihan freq data) | 3,934 |

## Interpretation

kHanyuPinlu orders readings by frequency and **explicitly lists
neutral-tone (toneless) forms** as separate readings. The current
heteronym map doesn't track neutral tones. That accounts for the
bulk of the "differences":

1. kHanyuPinlu's primary is often the toneless colloquial form
   (e.g. 乎 `hu`, 仙 `xian`, 伍 `wu`, 傅 `fu`, 卜 `bo`, 友 `you`).
   Using these as the **primary** would drop tone marks for the main
   glyph — not what the font wants.
2. The remaining differences are a mix of (a) real corrections worth
   adopting and (b) classical-corpus biases worth rejecting.

To filter, the patch list below considers only candidates where the
kHanyuPinlu primary has a tone mark **and** is already present in the
current heteronym set — i.e. reorderings of known readings, not new
claims. That filter yielded 64 candidates, hand-classified into three
buckets.

## Bucket A — Clearly wrong in current map

The current map's primary is either non-existent or a far-secondary
reading. Fix with high confidence.

| cp | char | current | → fix | reason |
|---|---|---|---|---|
| U+60F9 | 惹 | nuò | **rě** | current is wrong; 惹 has only one reading `rě` |
| U+6734 | 朴 | pò | **pǔ** | `pǔ` is the modern primary (朴素, 朴实); `pò` only in surname 朴 |
| U+7F3A | 缺 | guì | **quē** | current is wrong; 缺 has only one reading `quē` |
| U+901B | 逛 | guāng | **guàng** | current is wrong; 逛 has only one reading `guàng` |

## Bucket B — Modern-standard primary differs

Both readings exist, but the kHanyuPinlu primary aligns with modern
Standard Mandarin usage.

| cp | char | current | → fix | rationale |
|---|---|---|---|---|
| U+4E88 | 予 | yú | **yǔ** | `yǔ` = "give" is primary; `yú` is literary |
| U+4EC0 | 什 | shí | **shén** | 什么 is the overwhelmingly common usage |
| U+5360 | 占 | zhān | **zhàn** | 占有/占领 modern; `zhān` (divine) is archaic |
| U+5496 | 咖 | gā | **kā** | 咖啡 is the primary modern usage |
| U+573A | 场 | cháng | **chǎng** | 场所/现场/操场 dominate; `cháng` only in 一场雨 |
| U+5239 | 刹 | chà | **shā** | 刹车 modern primary; `chà` only in 刹那 |
| U+66F4 | 更 | gēng | **gèng** | 更加/更好 — modern function word, very high frequency |
| U+66FE | 曾 | zēng | **céng** | 曾经 modern adverb; `zēng` only in 曾祖 |
| U+6854 | 桔 | jié | **jú** | 桔子 modern; `jié` rare |
| U+69DB | 槛 | jiàn | **kǎn** | 门槛 modern; `jiàn` literary |
| U+6C13 | 氓 | méng | **máng** | 流氓 dominates modern usage |
| U+70AE | 炮 | páo | **pào** | 大炮/鞭炮 — `pào` is the primary; `páo` rare |
| U+7D2F | 累 | lěi | **lèi** | "tired" overwhelmingly more common than "accumulate" |
| U+7EA4 | 纤 | qiàn | **xiān** | 纤维/纤细 modern; `qiàn` (tow rope) rare |
| U+83CC | 菌 | jùn | **jūn** | 细菌/病菌 — `jūn` is the standard reading |
| U+8D9F | 趟 | tāng | **tàng** | measure word `tàng` (一趟) dominates; `tāng` only in 趟水 |
| U+8FD8 | 还 | huán | **hái** | 还是/还有 — extremely high frequency adverb |
| U+90FD | 都 | dū | **dōu** | 都 = "all" is one of the most common Chinese words |
| U+94A5 | 钥 | yuè | **yào** | 钥匙 modern uses `yào` |

## Bucket C — Both readings very common (skipped)

Both readings are productive in modern Standard Mandarin and `pǔtōnghuà`
corpora disagree on which is more frequent. The current map's choice is
defensible; do not change unless a specific corpus motivates it.

倒 dǎo/dào · 兴 xīng/xìng · 削 xiāo/xuē · 卷 juàn/juǎn · 咋 zé/zǎ ·
咽 yān/yàn · 哗 huá/huā · 尽 jìn/jǐn · 干 gān/gàn · 悄 qiǎo/qiāo ·
挣 zhèng/zhēng · 斗 dǒu/dòu · 晕 yùn/yūn · 泊 bó/pō · 漂 piāo/piào ·
煞 shà/shā · 率 shuài/lǜ · 琢 zhuó/zuó · 甚 shèn/shén · 畜 xù/chù ·
眯 mí/mī · 绷 bēng/běng · 缝 féng/fèng · 翘 qiáo/qiào · 脯 fǔ/pú ·
舍 shè/shě · 茄 gā/jiā · 蛤 gé/há · 调 tiáo/diào · 辟 bì/pì ·
逮 dài/dǎi · 量 liáng/liàng · 铺 pū/pù · 长 cháng/zhǎng · 为 wéi/wèi ·
似 sì/shì · 伺 sì/cì · 吭 háng/kēng · 咳 ké/hāi · 澎 péng/pēng ·
勒 lè/lēi

## What was actually applied

Of the 24 A+B fixes, only 12 required changes in `heteronym_map.json`
— the other 12 were **already correct** in `heteronym_map.json[cp][0]`
and only `pinyin_map.json` was stale. That stale cache has been deleted
(see git history of `sources/data/pinyin_map.json`).

The 12 entries whose slot 0 was reordered:

予 yú→**yǔ** · 什 shí→**shén** · 刹 chà→**shā** · 咖 gā→**kā** ·
朴 pò→**pǔ** · 桔 jié→**jú** · 槛 jiàn→**kǎn** · 氓 méng→**máng** ·
纤 qiàn→**xiān** · 菌 jùn→**jūn** · 还 huán→**hái** · 钥 yuè→**yào**
