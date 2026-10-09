# tabular-contract

A lightweight, dependency-free CSV profiler and data contract validator for the point where files enter a pipeline.

tabular-contract checks row shape, required columns, types, nullability, unique keys, and row-count bounds. It also reports inferred column types, distinct values, and empty cells so a data engineer can spot basic quality issues before loading data into a warehouse.

## Quick start

Requires Python 3.11 or newer.

~~~bash
python -m pip install .
tabular-contract examples/orders.csv --contract examples/orders.contract.json
~~~

Expected output:

~~~text
PASS  orders.csv
3 row(s) · 4 column(s)
  order_id: integer, 3 distinct, 0 empty
  customer_email: string, 3 distinct, 0 empty
  total: number, 3 distinct, 0 empty
  paid: boolean, 2 distinct, 0 empty
~~~

Use --format json for a machine-readable report that can be consumed by a pipeline:

~~~bash
tabular-contract examples/orders.csv --contract examples/orders.contract.json --format json
~~~

The JSON report includes the overall validity, row and column counts, per-column profile, and any validation errors. The process keeps the same exit codes in either output format.

## Contract format

Contracts are JSON files. Column types currently supported are string, integer, number, boolean, and ISO date. Columns are nullable unless nullable is set to false. A unique rule can name one column or a composite key.

~~~json
{
  "min_rows": 1,
  "max_rows": 100000,
  "columns": {
    "order_id": { "type": "integer", "nullable": false },
    "customer_email": { "type": "string", "nullable": false },
    "total": { "type": "number", "nullable": false }
  },
  "unique": ["order_id", ["customer_email", "order_id"]]
}
~~~

## Exit codes

- 0: file passes the supplied contract.
- 1: the CSV was read, but one or more quality rules failed.
- 2: the file or contract could not be read or parsed.

That makes the command usable as a lightweight gate in a local workflow or CI job.

## Scope

This is an early, intentionally small tool for CSV inputs. It does not replace warehouse constraints, schema registries, or full data observability platforms. It has no runtime dependencies outside the Python standard library.

## Development

~~~bash
python -m pip install -e .
python -m tabular_contract.cli examples/orders.csv --contract examples/orders.contract.json
~~~

## License

MIT. See LICENSE.
