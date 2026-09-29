# JOIN Test Model v2 / Template v4 semantics

The five dimensions describe observable behavior of one read-only JOIN query. A coverage claim is valid only when its SQL and expected rows express every assigned value.

| Dimension | Value | Required SQL or result behavior |
|---|---|---|
| `join_type` | `inner`, `left`, `right`, `full`, `cross` | The corresponding JOIN operator appears in SQL. |
| `predicate` | `none` | Only CROSS JOIN; no `ON` clause. |
| `predicate` | `equality`, `inequality`, `less_equal` | `ON a.k = b.k`, `a.k <> b.k`, or `a.k <= b.k`, respectively. `less_equal` is an ordered comparison, not an interval join. |
| `datatype` | `int`, `varchar`, `date` | Both JOIN keys use values of that type. `int` is explicitly cast to Xugu `INTEGER`; bare small integer literals would otherwise be inferred as `TINYINT`. |
| `null_side` | `none` | No JOIN output row has a NULL-extended key. |
| `null_side` | `left` | At least one output row has a NULL left key and a non-NULL right key, with no right-null row. |
| `null_side` | `right` | At least one output row has a NULL right key and a non-NULL left key, with no left-null row. |
| `null_side` | `both` | The result contains both a left-null row and a right-null row. |

`inner` and `cross` permit only `null_side=none`; `left` permits `none` or `right`; `right` permits `none` or `left`; `full` permits all four values. A one-sided NULL result on FULL JOIN uses a matched row plus an additional unmatched row. `both` uses unmatched rows on both sides. This definition concerns JOIN output NULL extension, not NULL values stored in the input keys.

The MVP `datatype=int` value covers Xugu `INTEGER` specifically. It does not claim separate coverage of `TINYINT`, `SMALLINT`, or `BIGINT`; those would require new model values and a new model version.

`interaction=none` executes the JOIN directly. `where` adds a sentinel row then removes it with an outer WHERE filter. `group_by` duplicates the JOIN result with `UNION ALL` then collapses the duplicates with GROUP BY. `subquery` adds a sentinel row then filters it through a correlated EXISTS expression. These interactions therefore affect the result before the final expected rows are compared.

The template derives Expected from its input rows and JOIN predicate. Static validation re-renders the assignment and requires exact SQL, Expected, and comparison-mode agreement. Real Xugu trial runs then check the declared Expected twice. The Model remains version `2`; the template and generator are version `4`. Version 3 introduced `less_equal` fixtures with values on the less-than, equality, and greater-than sides so changing `<=` to `<` changes the expected result. Version 4 explicitly casts `int` values to `INTEGER`, including sentinel rows. Earlier candidates and trial artifacts remain historical evidence and cannot be promoted under v4.
