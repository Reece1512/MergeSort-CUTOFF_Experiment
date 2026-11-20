# Lưới cutoff `e1,e1x`

## Độ lệch giữa các fork (CV (coefficient of variation) - hệ số biến thiên, tính theo %)

| distribution | n | cau_hinh | cv_trung_vi | cv_p90 | cv_max |
|---|---|---|---|---|---|
| random | 10000 | 85.00 | 3.98 | 7.12 | 8.76 |
| random | 100000 | 95.00 | 3.48 | 7.64 | 11.80 |
| random | 1000000 | 95.00 | 3.20 | 6.31 | 8.24 |

## Đối chứng nhiễu: t(1)/t(0)

15 dataset: trung vị 0.992, nhỏ nhất 0.927, lớn nhất 1.056. Lý tưởng là 1,000.

## CUTOFF tốt nhất theo phân bố và N

`rel_X` = thời gian của cutoff X chia cho thời gian của cutoff tốt nhất.

| phan_bo | N | datasets | nhom_tot_nhat | khong_khac_biet_thong_ke | cham_hon_<=_2% | rel_0 | rel_7 | rel_10 | ms_tot_nhat |
|---|---|---|---|---|---|---|---|---|---|
| random | 10000 | 5 | 40–77 | 20–77 | 20–77 | 1.119 | 1.092 | 1.060 | 1.452 |
| random | 100000 | 5 | 25–47 | 25–48 | 25–47 | 1.134 | 1.061 | 1.061 | 17.848 |
| random | 1000000 | 5 | 16–29 | 4–6, 8–60, 62–121 | 16–29 | 1.089 | 1.070 | 1.031 | 410.363 |

## Kết luận gộp: dữ liệu ngẫu nhiên, mọi N

- CUTOFF tốt nhất: **25**
- Không khác biệt có ý nghĩa thống kê với 25: 25–47
- Chậm hơn 25 không quá 2%: 20–23, 25–48
- Bootstrap (2000 lần): 25 thắng 86% số lần; các cutoff chiếm 90% số lần thắng: 25, 30
- Thời gian tương đối: cutoff 0 = 1.113, 7 = 1.074, 10 = 1.050

## So sánh cặp

Tỉ số > 1 nghĩa là cutoff đứng trước chậm hơn.

| phan_bo | N | so_sanh | datasets | ti_so | ci95_thap | ci95_cao | p | cham_hon_o |
|---|---|---|---|---|---|---|---|---|
| random | 10000 | 0 vs 40 | 5 | 1.1191 | 1.1085 | 1.1299 | 0.0000 | 5/5 |
| random | 10000 | 7 vs 40 | 5 | 1.0920 | 1.0756 | 1.1087 | 0.0001 | 5/5 |
| random | 10000 | 10 vs 40 | 5 | 1.0601 | 1.0222 | 1.0994 | 0.0113 | 5/5 |
| random | 10000 | 7 vs 10 | 5 | 1.0301 | 1.0030 | 1.0579 | 0.0366 | 5/5 |
| random | 100000 | 0 vs 25 | 5 | 1.1336 | 1.1088 | 1.1590 | 0.0001 | 5/5 |
| random | 100000 | 7 vs 25 | 5 | 1.0613 | 1.0372 | 1.0860 | 0.0020 | 5/5 |
| random | 100000 | 10 vs 25 | 5 | 1.0613 | 1.0372 | 1.0860 | 0.0020 | 5/5 |
| random | 100000 | 7 vs 10 | 5 | 1.0000 |  |  |  | 0/5 |
| random | 1000000 | 0 vs 16 | 5 | 1.0885 | 1.0315 | 1.1487 | 0.0119 | 5/5 |
| random | 1000000 | 7 vs 16 | 5 | 1.0701 | 1.0170 | 1.1260 | 0.0209 | 5/5 |
| random | 1000000 | 10 vs 16 | 5 | 1.0310 | 0.9786 | 1.0863 | 0.1797 | 4/5 |
| random | 1000000 | 7 vs 10 | 5 | 1.0379 | 1.0052 | 1.0716 | 0.0321 | 5/5 |
| random (mọi N) |  | 0 vs 25 | 15 | 1.1128 | 1.0934 | 1.1326 | 0.0000 | 15/15 |
| random (mọi N) |  | 7 vs 25 | 15 | 1.0737 | 1.0570 | 1.0905 | 0.0000 | 15/15 |
| random (mọi N) |  | 10 vs 25 | 15 | 1.0500 | 1.0304 | 1.0700 | 0.0001 | 14/15 |
| random (mọi N) |  | 7 vs 10 | 15 | 1.0225 | 1.0088 | 1.0365 | 0.0033 | 10/15 |

![e1+e1x_curves](../../report/figures/e1+e1x_curves.png)
