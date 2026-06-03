# 42 A-Share Listed Banks

> Data source: Shanghai/Shenzhen Stock Exchange. Last updated: 2026-05.

## Large State-Owned Banks (6)

| # | Code | Name | Type Override |
|---|------|------|---------------|
| 1 | SH601398 | 工商银行 | traditional_commercial |
| 2 | SH601939 | 建设银行 | traditional_commercial |
| 3 | SH601288 | 农业银行 | traditional_commercial |
| 4 | SH601988 | 中国银行 | traditional_commercial |
| 5 | SH601328 | 交通银行 | traditional_commercial |
| 6 | SH601658 | 邮储银行 | traditional_commercial |

## Joint-Stock Banks (9)

| # | Code | Name | Type Override |
|---|------|------|---------------|
| 7 | SH600036 | 招商银行 | integrated |
| 8 | SH601166 | 兴业银行 | integrated |
| 9 | SH600016 | 民生银行 | traditional_commercial |
| 10 | SH600000 | 浦发银行 | traditional_commercial |
| 11 | SH601818 | 光大银行 | traditional_commercial |
| 12 | SH600015 | 华夏银行 | traditional_commercial |
| 13 | SZ000001 | 平安银行 | integrated |
| 14 | SH601998 | 中信银行 | traditional_commercial |
| 15 | SH601916 | 浙商银行 | traditional_commercial |

## City Commercial Banks (17)

| # | Code | Name | Type Override |
|---|------|------|---------------|
| 16 | SZ002142 | 宁波银行 | traditional_commercial |
| 17 | SH601009 | 南京银行 | traditional_commercial |
| 18 | SH601229 | 上海银行 | traditional_commercial |
| 19 | SH600926 | 杭州银行 | traditional_commercial |
| 20 | SH601838 | 成都银行 | traditional_commercial |
| 21 | SH601997 | 贵阳银行 | traditional_commercial |
| 22 | SH601169 | 北京银行 | traditional_commercial |
| 23 | SH601577 | 长沙银行 | traditional_commercial |
| 24 | SH601963 | 重庆银行 | traditional_commercial |
| 25 | SH601528 | 瑞丰银行 | traditional_commercial |
| 26 | SH601860 | 紫金银行 | traditional_commercial |
| 27 | SH601187 | 厦门银行 | traditional_commercial |
| 28 | SH601825 | 沪农商行 | traditional_commercial |
| 29 | SH601665 | 齐鲁银行 | traditional_commercial |
| 30 | SH601128 | 常熟银行 | traditional_commercial |
| 31 | SH601077 | 渝农商行 | traditional_commercial |
| 32 | SH600908 | 无锡银行 | traditional_commercial |

## Rural Commercial Banks (10)

| # | Code | Name | Type Override |
|---|------|------|---------------|
| 33 | SH603323 | 苏农银行 | traditional_commercial |
| 34 | SZ002839 | 张家港行 | traditional_commercial |
| 35 | SZ002807 | 江阴银行 | traditional_commercial |
| 36 | SZ002958 | 青农商行 | traditional_commercial |
| 37 | SH600928 | 西安银行 | traditional_commercial |
| 38 | SH600919 | 江苏银行 | traditional_commercial |
| 39 | SZ002936 | 郑州银行 | traditional_commercial |
| 40 | SZ002948 | 青岛银行 | traditional_commercial |
| 41 | SZ001227 | 兰州银行 | traditional_commercial |
| 42 | SZ002966 | 苏州银行 | traditional_commercial |

## Notes

- Type overrides are used as fallback when API interest income ratio data is unavailable.
- `traditional_commercial`: Interest income > 60% of revenue (default for Chinese banks).
- `integrated`: 40% < interest income ratio <= 60%, diversified revenue streams.
- Type classification is verified against API data during Phase 2; overrides only apply when data is missing.
- The six large state-owned banks are classified as traditional_commercial due to their deposit-and-loan business model dominance.
