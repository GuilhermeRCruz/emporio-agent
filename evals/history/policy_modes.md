# Policy lookup: three modes compared

All on gemini-3.5-flash with minimal thinking, judge gemini-2.5-flash, the 11 policy cases run
3 times per mode (33 runs each). Raw results per run are in the folders next to this file.

## Round 1: three modes, run in parallel (`three_modes/`)

| Mode | Passed | Right section retrieved | Median latency |
|---|---|---|---|
| sections | 30/33 | 28/30 | 2.47s |
| rag (3 subsection chunks) | 32/33 | 30/30 | 3.07s |
| rag_parent (whole sections of the matching chunks) | 32/33 | 30/30 | 3.07s |

* sections failed twice on the mouthpiece question without calling the tool at all: the model
  took it for an accessories question. The tool only listed bare section names.
* rag failed the warranty follow-up once: the chunk with the store's help on manufacturer
  warranty was not among the three returned.
* rag and rag_parent tied on accuracy and latency. rag was removed: rag_parent cannot cut the
  context a follow-up needs, for about 76 extra tokens per case.

## Round 2: sections with described contents vs rag_parent, run sequentially (`sections_vs_parent/`)

The sections tool now says what each section contains (for example that exchanges include
"items that cannot be exchanged: mouthpieces of wind instruments").

| Mode | Passed | Right section retrieved | Median latency | Mean latency | Mean input tokens |
|---|---|---|---|---|---|
| **sections** | **33/33** | **30/30** | **2.41s** | **2.84s** | 6528 |
| rag_parent | 32/33 | 30/30 | 2.88s | 3.24s | 6031 |

Sections is the default: as accurate or better, and about 0.45s faster per policy question,
because RAG always pays an embedding round trip. It costs about 500 more input tokens per case
(the longer tool description). rag_parent stays available for a manual too large for a
section lookup.
