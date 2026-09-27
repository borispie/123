# 栏目模板

`make_post_pack.py` 按星期几选模板。每个模板分三段：`## 主贴`、`## 回复`、`## 短推`。

- `{变量}` 会自动从 `data/日期.csv` 和 `data/predictions.xlsx` 填。拉不到就变成【需补充：变量名】。
- 直接写在模板里的【需补充：xxx】是要你自己查了填的。
- 可用变量见 `scripts/make_post_pack.py` 里的 `build_vars()`，常用的：
  - `{BTC_tag}` → `$BTC（我持有）`，没持有的币就是 `$ETH`
  - `{BTC_price}` `{BTC_24h}` `{BTC_7d}` `{BTC_30d}`（ETH/SOL/BNB/HYPE 同理）
  - `{best_7d}` `{best_7d_pct}` `{worst_7d}` `{worst_7d_pct}`
  - `{etf_BTC}` `{etf_ETH}` `{etf_date}`
  - `{unlock_list}`
  - `{pred_week_brier}` `{pred_all_brier}` `{pred_count}` `{pred_settled_list}` `{pred_new_list}`
  - `{sources}`（放在回复里）
