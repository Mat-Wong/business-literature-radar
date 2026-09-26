# 检索范围与数据接口 / Search scope and data interfaces

## 用户选择的是期刊与预印本

网页中的“文献来源”包括 UTD24 期刊、arXiv 与 SSRN。UTD24 期刊按所选学科默认勾选，也可逐本调整。目录依据 [UTD 官方期刊列表](https://jsom.utdallas.edu/the-utd-top-100-business-school-research-rankings/list-of-journals)。学科与期刊的对应关系用于方便选择，不是 UTD 官方学科分类。

Econ 是研究主题方向，不代表经济学五大刊属于 UTD24。当前网页可在所选商科期刊与 SSRN 中查找经济学相关研究。

## 开发者使用的数据接口

底层通过 OpenAlex、Crossref、Semantic Scholar 等接口获取题名、摘要、DOI 与期刊信息；arXiv 使用其公开接口，SSRN 线索由公开索引提供。引擎保留 DBLP 等跨学科接口供源码工作流使用。这些接口是数据获取渠道，不是用户选择的目标期刊，也不代表与出版社或 UTD 有合作关系。

网页按期刊及预印本范围筛选展示结果，JSON 中仍保留原始接口来源，便于核对。期刊名匹配依赖索引记录；缺失或误标的记录可能无法识别。摘要和 SSRN 记录不一定完整，未提供摘要时不会补写。检索结果不等于 UTD 官方全文数据库，也不保证覆盖目标期刊全部论文。

## English

The web app lets researchers choose UTD24 journals, arXiv and SSRN—not metadata APIs. Journal defaults follow the selected disciplines and can be edited individually. The journal list follows the [official UTD directory](https://jsom.utdallas.edu/the-utd-top-100-business-school-research-rankings/list-of-journals); discipline mappings are this project's convenience, not official UTD classifications. Econ is a research direction, not an assertion that the economics top five belong to UTD24.

The engine retrieves bibliographic records through OpenAlex, Crossref, Semantic Scholar and the arXiv API. SSRN leads come from public indexes. DBLP remains available in source-based workflows. These are technical retrieval channels, not publishers or endorsements. The web app filters displayed papers by the chosen journal/preprint scope while JSON retains original API provenance. Missing or incorrect journal metadata can affect matching; abstracts and SSRN coverage may be incomplete. This is not the official UTD full-text database and does not guarantee exhaustive coverage.
