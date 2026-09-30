# 창고 재고 통합 리포트

- 저재고 기준(low_stock_basis): `warehouse_row`
- 임계값(threshold): 5 (quantity < 5)
- 원본 파일: warehouse-a.md, warehouse-b.md, warehouse-c.md
- 전체 합계(grand_total): 54

## 창고별 합계 (warehouse_totals)

| 창고 | 합계 |
| --- | --- |
| A | 22 |
| B | 16 |
| C | 16 |

## 품목별 전체 수량 (item_totals)

| 품목 | 총 수량 |
| --- | --- |
| mug | 17 |
| bottle | 12 |
| sensor | 11 |
| hub | 13 |
| cable | 1 |

## 저재고 목록 (low_stock)

| 창고 | 품목 | 수량 |
| --- | --- | --- |
| A | bottle | 3 |
| B | hub | 2 |
| C | sensor | 4 |
| C | cable | 1 |
