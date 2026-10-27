# Why ambiguous records go to review

In the sample mapping, the alias `pressure unit` could mean `PUMP` or `SENSOR`. The pipeline could pick one (the first listed, the more frequent, a fuzzy "closest" match), and the output would look just as clean either way. But the choice would be invented, and a wrong guess changes business meaning (a sensor counted as a pump) without leaving any trace.

So the pipeline refuses: the row is written to `exceptions.csv` with its source row number, the raw text, the candidate targets (`PUMP, SENSOR`) and the code `AMBIGUOUS_CATEGORY`. A person can resolve the alias once (by editing the mapping so it has one target) and rerun; the same rule then applies deterministically to every affected row.

The same reasoning applies to `03/04/2024` (day/month order unknown), blank quantities (missing is not zero) and duplicated IDs (which occurrence is right is unknown). The cost is more rows to review; the benefit is that every accepted row can be traced to its source and nothing in the clean file was guessed.

This note describes this demo only.
