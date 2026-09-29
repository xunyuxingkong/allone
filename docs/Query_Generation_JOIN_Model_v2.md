# JOIN Test Model v2 semantics

The five dimensions describe observable behavior of one read-only JOIN query. A coverage claim is valid only when its SQL and expected rows express every assigned value.

| Dimension | Value | Required SQL or result behavior |
|---|---|---|
| `join_type` | `inner`, `left`, `right`, `full`, `cross` | The corresponding JOIN operator appears in SQL. |
| `predicate` | `none` | Only CROSS JOIN; no `ON` clause. |
| `predicate` | `equality`, `inequality`, `less_equal` | `ON a.k = b.k`, `a.k <> b.k`, or `a.k <= b.k`, respectively. `less_equal` is an ordered comparison, not an interval join. |
| `datatype` | `int`, `varchar`, `date` | Both JOIN keys use literals of that type. |
| `null_side` | `none` | No JOIN output row has a NULL-extended key. |
| `null_side` | `left` | At least one output row has a NULL left key and a non-NULL right key, with no right-null row. |
| `null_side` | `right` | At least one output row has a NULL right key and a non-NULL left key, with no left-null row. |
| `null_side` | `both` | The result contains both a left-null row and a right-null row. |

`inner` and `cross` permit only `null_side=none`; `left` permits `none` or `right`; `right` permits `none` or `left`; `full` permits all four values. A one-sided NULL result on FULL JOIN uses a matched row plus an additional unmatched row. `both` uses unmatched rows on both sides. This definition concerns JOIN output NULL extension, not NULL values stored in the input keys.

`interaction=none` executes the JOIN directly. `where` adds a sentinel row then removes it with an outer WHERE filter. `group_by` duplicates the JOIN result with `UNION ALL` then collapses the duplicates with GROUP BY. `subquery` adds a sentinel row then filters it through a correlated EXISTS expression. These interactions therefore affect the result before the final expected rows are compared.

The template derives Expected from its input rows and JOIN predicate. Static validation re-renders the assignment and requires exact SQL, Expected, and comparison-mode agreement. Real Xugu trial runs then check the declared Expected twice. Model and template versions are `2`; version `1` candidates and trial artifacts remain historical evidence and cannot be promoted under v2.
