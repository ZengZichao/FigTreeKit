# FigTreeKit

**系统发育树 FigTree 可视化样式编程工具**

[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/downloads/)
[![License: GPL v2+](https://img.shields.io/badge/License-GPL%20v2+-blue.svg)](https://www.gnu.org/licenses/old-licenses/gpl-2.0.html)
[![Version](https://img.shields.io/badge/version-1.0.1-green.svg)](https://pypi.org/project/figtreekit/)
[![Bioinformatics](https://img.shields.io/badge/topic-bioinformatics-green.svg)](https://github.com/ZengZichao/FigTreeKit)

[English](https://github.com/ZengZichao/FigTreeKit/blob/main/README_EN.md) | [中文](#)

---

## 概述

FigTreeKit 是一个 Python 库，用于系统发育树的程序化出版级样式设置。它解决了进化生物学和比较基因组学中**可复现、可脚本化的树可视化**问题——将原始 Newick/Nexus 树转换为带注解的、出版级质量的图形，兼容 [FigTree](http://tree.bio.ed.ac.uk/software/figtree/)。

典型使用场景：
- 对系统发育基因组学树进行分类群高亮
- 批量处理数百棵基因树，保持一致的格式
- 按分类群名称验证和折叠分支
- 从 BEAST/RAxML/IQ-TREE 输出生成出版级图片

### 核心特性

- **FigTree 兼容输出**：生成带 `[&!hilight]`、`[&!color]`、`[&!font]` 注解的 Nexus 文件
- **Pythonic API**：方法链式调用，直观的树样式设置
- **分类学感知分析**：自动从标签提取分类信息（嵌入式 `_d_`/`_p_`/`_g_`/`_s_`/`_ss_` 格式和表格 `d__`/`p__` 格式）
- **单系群检测**：检测类群是否为单系群，支持特殊标识符（LUCA/LACA/LBCA）
- **分支折叠**：按分类群名称折叠分支，带单系性验证
- **多树处理**：检测并处理多棵树，支持 `split`/`first`/`last`/`random` 模式
- **深度输入验证**：结构检查、负分支检测、重复末端名、恶意字符扫描
- **实时日志**：ISO 8601 时间戳、stdout 刷新、可选日志文件输出
- **自检模式**：`--self-test` 验证依赖、解析、分类学和单系群逻辑
- **批量处理**：通过 CLI 处理多个树文件
- **图片渲染**：无需打开 FigTree GUI 即可导出 PNG/PDF/SVG（需要 FigTree JAR）；若只需命令行直接渲染超大规模树，也可考虑 [TreeViewer](https://doi.org/10.1002/ece3.10873)

---

## 与现有工具对比

| 能力 | FigTreeKit | FigTree GUI | DendroPy | ETE3 | TreeViewer |
| --- | :---: | :---: | :---: | :---: | :---: |
| 程序化/脚本化样式 | ✅ | ❌ | ⚠️ 有限 | ⚠️ 有限 | ✅ (CLI) |
| Python API | ✅ | ❌ | ✅ | ✅ | ❌ |
| 注入 FigTree 注解（`!hilight`/`!color`/`!font`） | ✅ | N/A | ❌ | ❌ | ❌ |
| 分类学感知折叠 / 单系群检测 | ✅ | 手动 | ⚠️ 部分 | ⚠️ 部分 | ❌ |
| 深度输入验证（括号、负分支、恶意字符等） | ✅ | ❌ | ❌ | ❌ | ❌ |
| 批量 CLI 处理 | ✅ | ❌ | ❌ | ✅ | ✅ |
| 图片渲染（PNG/PDF/SVG） | ✅ | ✅ | ❌ | ✅ | ✅ |

完整功能矩阵与复现方法见 [docs/comparison_CN.md](docs/comparison_CN.md)。

---

## 安装

### 从 PyPI 安装（推荐）

```bash
pip install figtreekit
```

### 从源码安装

```bash
git clone https://github.com/ZengZichao/FigTreeKit.git
cd FigTreeKit
pip install -r requirements.txt
pip install -e .
```

### 依赖项

- **必需**：Python 3.11，Biopython (>=1.80, <2.0)
- **可选**：psutil（内存日志），Java 8+（渲染）
- **测试平台**：macOS Tahoe 26.5.2（Apple Silicon）

### 自检

安装后验证：

```bash
figtreekit --self-test
```

详见快速开始章节的预期输出。

---

## 快速开始

### 1. 验证安装

```bash
figtreekit --self-test
```

```
  [PASS]   Dependency: biopython
  [PASS]   Dependency: python
  [PASS]   Parse: Newick example
  [PASS]   Taxonomy: embedded format extraction
  [PASS]   Taxonomy: table format extraction
  [PASS]   Monophyly: Cyanobacteriales (monophyletic)
  [PASS]   Special ID: LUCA resolves all taxa
  [PASS]   Special ID: LACA resolves Archaea only
  [PASS]   Export: Newick → Nexus round-trip
  [PASS]   Validation: FASTA example
  [PASS]   Security: control char detection
  All 11 checks passed.
```

### 2. Python API

```python
from figtreekit import FigTreeStyler, LayoutType, FontStyle

styler = FigTreeStyler().load_content("((A:0.1,B:0.2):0.3,(C:0.4,D:0.5):0.6);")
styler.set_layout(LayoutType.RECTILINEAR)
styler.set_appearance(background_color="#FAFAFA", branch_line_width=2.0)
styler.highlight_clade(["A", "B"], color="#FF0000")
styler.set_tip_labels(is_shown=True, font_size=12)
styler.export("output.nex")
```

### 3. 命令行

```bash
figtreekit input.tre -o output.nex --layout polar --tip-labels-show
figtreekit input.tre --validate
figtreekit input.tre -o output.nex --clade Cyanobacteriota
```

### 4. 导出并渲染为图片

```bash
figtreekit --setup-figtree              # 一次性设置
figtreekit input.tre -o output.nex --render tree.png
figtreekit input.tre -o output.nex --render tree.pdf --render-width 1600
```

---

## 分类学分析

### 自动分类学提取

FigTreeKit 支持两种格式的分类学提取：

**格式 A（嵌入式）** — 分类信息编码在标签中：
```
GB_GCA_000252485.1_d_Bacteria_p_Cyanobacteriota_c_Cyanobacteriia_o_Cyanobacteriales_f_Prochloraceae_g_Prochloron
```

**格式 B（表格）** — 分号分隔的分类字符串：
```
d__Archaea;p__Thermoproteota;c__Korarchaeia;o__Korarchaeales;f__Korarchaeaceae;g__WALU01;s__
```

### Python API

```python
from figtreekit import FigTreeStyler

styler = FigTreeStyler("tree.nwk")

# 按类群名检查单系性（自动检测格式）
result = styler.check_monophyly_by_group("Cyanobacteriales")
print(result["is_monophyletic"])  # True/False
print(result["resolved_taxa"])    # 分类单元列表

# 折叠单系群
styler.collapse_by_group("Cyanobacteriales")
styler.export("collapsed.nex")
```

### CLI 用法

```bash
figtreekit tree.nwk -o collapsed.nex --clade Cyanobacteriota
figtreekit tree.nwk -o collapsed.nex --clade Cyanobacteriota --strict
figtreekit tree.nwk -o out.nex --clade Cyanobacteriota --clade Proteobacteria
figtreekit tree.nwk -o out.nex --taxonomy-delimiter-mode greedy
figtreekit tree.nwk -o out.nex --taxonomy-table-sep "|"
figtreekit tree.nwk -o out.nex --taxonomy-levels "k:kingdom,ss:subspecies"
```

### 特殊标识符

| 标识符 | 描述 |
|--------|------|
| `LUCA` | 最后共同祖先（所有 Bacteria + Archaea） |
| `LACA` | 最后古菌共同祖先 |
| `LBCA` | 最后细菌共同祖先 |
| `root` | 树的根节点（所有末端） |

```python
result = styler.check_monophyly_by_group("LUCA")
```

### 外部分类学表格

当标签不含分类信息时，可提供映射文件（TSV/CSV，两列格式）。详见输入格式详情章节。

```bash
figtreekit tree.nwk -o out.nex --clade Cyanobacteriales
```

---

## 多树处理

当文件包含多棵树时：

```bash
figtreekit multi.nex -o out.nex                    # 默认：打印摘要并终止（退出码 2）
figtreekit multi.nex -o out.nex --multi-tree split  # 处理所有树，输出带数字后缀
figtreekit multi.nex -o out.nex --multi-tree first  # 仅处理第一棵树
figtreekit multi.nex -o out.nex --multi-tree last   # 仅处理最后一棵树
figtreekit multi.nex -o out.nex --multi-tree random # 随机选择一棵树
figtreekit multi.nex -o out.nex --multi-tree all    # 同 split，处理所有树
```

---

## 序列验证

FigTreeKit 可验证 FASTA/FASTQ 文件：

```bash
figtreekit sequences.fasta --validate
figtreekit sequences.fasta --validate --mol-type DNA
figtreekit aligned.fasta --validate --skip-length-check
figtreekit tree.nwk -o out.nex --sequences sequences.fasta
figtreekit tree.nwk --validate --sequences sequences.fasta
```

> **注意**：对序列文件（FASTA/FASTQ）使用 `--validate` 时，深度验证通过后返回退出码 0（成功），即使该文件不是树格式。这允许在脚本中对序列文件进行独立的验证流程。

检查项包括：
- 重复序列 ID（ERROR）
- 字母表验证（DNA/RNA/protein）并报告无效字符行号
- 比对长度一致性（WARNING）

详见输入格式详情章节的 FASTA/FASTQ 格式规范。

---

## 深度输入验证

### 树文件

| 检查项 | 级别 |
|--------|------|
| 括号平衡（圆括号、方括号） | ERROR（带位置） |
| 负分支长度 | CRITICAL（终止） |
| 空节点名 | ERROR |
| 重复末端名 | ERROR |
| 自循环检测 | ERROR |
| 控制字符 / Unicode 双向文本 | CRITICAL（终止） |

### 序列文件

| 检查项 | 级别 |
|--------|------|
| 重复序列 ID | ERROR（终止） |
| 字母表无效字符 | ERROR（带行号） |
| 比对长度不一致 | WARNING |

### 对抗性输入防护

- 控制字符（`\x00`-`\x1f`）→ CRITICAL
- Unicode 双向文本覆盖（`\u202E`）→ CRITICAL
- 分类学表格循环依赖 → ERROR
- 空文件（0 字节）→ CRITICAL

---

## 输出格式

### Nexus 文件结构

FigTreeKit 导出 FigTree 兼容的 Nexus 文件，包含三个块：

```
#NEXUS
begin taxa;
    dimensions ntax=3;
    taxlabels A B C ;
end;
begin trees;
    tree TREE1 = ((A:0.1,B:0.2):0.3,C:0.4);
end;
begin figtree;
    set appearance.backgroundColour=#ffffff;
    set layout.layoutType=POLAR;
    set tipLabels.isShown=true;
end;
```

### 注解格式

| 注解 | 格式 | 描述 |
|------|------|------|
| `!hilight` | `[&!hilight={tipCount,height,color}]` | clade 背景高亮 |
| `!color` | `[&!color=#RRGGBB]` | 分支颜色 |
| `!font` | `[&!font=Name-STYLE-size]` | 字体注解（Java `Font.decode()` 格式） |
| `!stroke` | `[&!stroke=N]` | 分支描边宽度（前向兼容） |

### 输出文件命名

| 模式 | 输出模式 |
|------|---------|
| 单棵树 | `<output>.nex`（用户指定） |
| 批量 | `<input_stem>.nex` 在输出目录中 |
| 多树 split | `<output>_tree1.nex`、`<output>_tree2.nex`、... |
| 折叠 clade | 同输入（clade 就地替换） |

---

## 输入格式详情

### 格式标准

FigTreeKit 遵循以下标准：
- **Newick**：[Newick 树格式](https://en.wikipedia.org/wiki/Newick_format) — 分支长度为替换单位（距父节点的进化距离）
- **Nexus**：[Nexus 文件格式](https://en.wikipedia.org/wiki/Nexus_file) — 符合 Maddison et al. (1997) 规范
- **FASTA**：[FASTA 格式](https://www.ncbi.nlm.nih.gov/genbank/fastaformat/) — 标准生物信息学序列格式
- **FASTQ**：[FASTQ 格式](https://en.wikipedia.org/wiki/FASTQ_format) — Illumina/Sanger 质量编码

### 树文件格式

**Newick**（`.nwk`, `.newick`, `.tree`, `.tre`, `.treefile`, `.nh`, `.nhy`, `.nhx`）：
```
((A:0.1,B:0.2):0.3,C:0.4);
```
- 分支长度可选（默认：不显示分支长度）
- 支持引号名称：`('Species A':0.1,'Species B':0.2);`
- 保留括号注释：`(A:0.1[&posterior=0.95],B:0.2);`

**Nexus**（`.nex`, `.nexus`, `.nx`）：
- 支持 translate block（BEAST 格式）
- 保留所有树（全部写入输出）
- 解析并合并现有的 `figtree` block
- **BEAST 输出**：translate block 和括号注释（如 `[&posterior=0.95]`）被保留

### 分类学映射文件

**两列格式**（自动检测 TSV/CSV）：

有表头：
```
name	taxonomy
GB_GCA_000252485.1	d__Bacteria;p__Cyanobacteriota;c__Cyanobacteriia;o__Cyanobacteriales;f__Prochloraceae;g__Prochloron;s__
RS_GCF_000013425.1	d__Archaea;p__Euryarchaeota;c__Methanomicrobia;o__Methanosarcinales;f__Methanosarcinaceae;g__Methanosarcina;s__
```

无表头：
```
GB_GCA_000252485.1	d__Bacteria;p__Cyanobacteriota;c__Cyanobacteriia;o__Cyanobacteriales;f__Prochloraceae;g__Prochloron;s__
```

- 分隔符：tab（`.tsv`）或逗号（`.csv`），自动检测
- 强制分隔符：`--table-sep ","`
- 缺失等级（如 `s__` 无值）→ 存储为空字符串
- 格式错误行：`--ignore-malformed` 跳过而非终止

### 支持的输入格式汇总

| 类型 | 格式 | 扩展名 |
|------|------|--------|
| 树 | Newick | `.nwk`, `.newick`, `.tree`, `.tre`, `.treefile`, `.nh`, `.nhy`, `.nhx` |
| 树 | Nexus | `.nex`, `.nexus`, `.nx` |
| 树 | PhyloXML † | `.xml`, `.phyloxml` |
| 序列 | FASTA | `.fasta`, `.fa`, `.fas`, `.fna`, `.faa`, `.ffn`, `.frn` |
| 序列 | FASTQ | `.fastq`, `.fq` |
| 序列 | GenBank | `.gb`, `.gbk`, `.genbank` |
| 序列 | EMBL | `.embl` |
| 序列 | Stockholm | `.stockholm`, `.sto` |
| 序列 | Phylip | `.phylip`, `.phy` |
| 序列 | Clustal | `.clustal`, `.aln` |
| 分类学 | TSV/CSV | `.tsv`, `.csv` |

> **† 格式支持范围：** 树的*样式化与渲染*（`FigTreeStyler` 与 Nexus 导出）**仅支持 Newick 与 Nexus**。PhyloXML 可被输入*校验器*（`--validate`）识别，但树样式器**不会**加载、样式化或渲染它。序列格式（FASTA、FASTQ、GenBank、EMBL、Stockholm、Phylip、Clustal）仅用于**输入校验与树↔序列交叉验证**（`--validate` / `--sequences`），而非树样式化。

### 处理流程

```
输入文件
    │
    ▼
┌─────────────────┐
│  格式检测        │  (Newick / Nexus / FASTA / FASTQ)
└────────┬────────┘
         ▼
┌─────────────────┐
│  深度验证        │  (括号、分支长度、重复、恶意字符)
└────────┬────────┘
         ▼
┌─────────────────┐
│ 多树检查         │  (ask / split / first / last / random / all)
└────────┬────────┘
         ▼
┌─────────────────┐
│ 分类学解析       │  (嵌入式 _d_/_p_ 或表格 d__/p__)
└────────┬────────┘
         ▼
┌─────────────────┐
│ 样式与折叠       │  (clade 高亮、颜色、单系性检查)
└────────┬────────┘
         ▼
┌─────────────────┐
│  导出 / 渲染     │  (Nexus 输出，可选 PNG/PDF/SVG)
└─────────────────┘
```

### 常见问题与边界情况

- **引号分类单元名**：含空格或特殊字符的名称必须在 Newick 中单引号包裹
- **缺失分支长度**：无分支长度的树有效；FigTree 将显示等长分支
- **多歧分支**：未解析节点（超过 2 个子节点）完全支持
- **Translate block**：BEAST 风格的数字分类 ID 自动解析
- **编码**：带 BOM（UTF-8-sig）或旧编码（latin-1）的文件透明处理
- **大树**：超过 10,000 个末端的树触发资源警告；使用 `--low-memory` 模式
- **空分类名**：检测并拒绝为 ERROR（无法映射分类学）
- **重复末端名**：检测并拒绝为 ERROR（会导致分类学映射冲突）

---

## 实时日志

所有操作产生带 ISO 8601 时间戳的实时日志输出：

```
2026-06-13T15:30:56.135 | [    INFO] | >>> Input file validation ...
2026-06-13T15:30:56.135 | [    INFO] | <<< Input file validation (0 ms)
2026-06-13T15:30:56.135 | [    INFO] | >>> Parsing tree file ...
2026-06-13T15:30:56.192 | [    INFO] | tree.nwk: parsed successfully, 3 taxa detected
2026-06-13T15:30:56.192 | [    INFO] | <<< Parsing tree file (57 ms)
2026-06-13T15:30:56.192 | [    INFO] | tree.nwk: DONE (total 0.06 s)
```

### 日志级别

| 标志 | 级别 | 描述 |
|------|------|------|
| `-q` | ERROR | 抑制所有非错误输出 |
| （默认） | WARNING | 仅警告和错误 |
| `-v` | INFO | 正常操作流程 |
| `-vv` | DEBUG | 详细调试信息 |

### 日志文件

```bash
figtreekit tree.nwk -o out.nex --log-file figtreekit.log
```

---

## 命令行接口

### 基本命令

```bash
figtreekit input.tre -o output.nex [OPTIONS]
figtreekit input.tre --validate
figtreekit --version
figtreekit --self-test
figtreekit --help
```

### 常用选项

> 完整且最新的选项列表请运行 `figtreekit --help` 查看。

```
位置参数:
  input                 输入树文件或批量处理目录

选项:
  -o, --output OUTPUT   输出 Nexus 文件（或批量输出目录）
  --validate            仅检查兼容性不导出
  -v, --verbose         增加详细度 (-v INFO, -vv DEBUG)（默认: WARNING）
  -q, --quiet           抑制非错误输出
  --version             显示版本、Git 提交哈希、日期和依赖
  --self-test           运行自诊断检查
  --config FILE         JSON 配置文件
  --log-file FILE       将日志写入文件（UTF-8, 所有级别）
  --force               覆盖已有输出文件
  --no-clobber          输出存在时跳过
  --strip-annotations   移除树中的括号注释（NHX/bootstrap/posterior）以减小文件体积

树:
  --clade NAME          按分类群名称折叠 clade
  --strict              非单系群时终止（默认: 警告并跳过）
  --multi-tree MODE     多树处理（默认: ask）
                        选项: ask/split/first/last/random/all
  --rooted              设置树为有根树
  --unrooted            设置树为无根树（与 --rooted 互斥时优先生效）

分类学:
  --taxonomy-levels SPEC          扩展等级前缀（如 "k:kingdom,ss:subspecies"）
  --taxonomy-delimiter-mode MODE  reverse/greedy/segment（默认: reverse）
  --taxonomy-table-sep CHAR       分类字符串分隔符（默认: ";"）
  --taxonomy-source-priority P    embedded/table（默认: table）
  --taxonomy-mapping-file FILE    分类学映射文件路径（TSV/CSV）
  --table-sep CHAR                强制映射文件列分隔符
  --ignore-malformed              跳过格式错误的分类学行

序列:
  --mol-type TYPE       DNA/RNA/protein（默认: 自动检测）
  --sequences FILE      序列文件，用于与树末端交叉验证
  --no-cross-check      跳过树-序列标签交叉验证
  --skip-length-check   跳过比对长度检查
  --low-memory          降低大文件内存使用（流式模式）

渲染:
  --render FILE               渲染树为图片（PNG/PDF/SVG/JPEG）
  --render-format FORMAT      强制指定渲染格式（PNG/PDF/SVG/JPEG）
  --render-width PX           图片宽度（默认: 1200）
  --render-height PX          图片高度（默认: 800）
  --figtree-jar PATH          figtree.jar 路径
  --setup-figtree             下载/编译 FigTree JAR
  --check-figtree             检查 FigTree JAR 是否可用
```

### 配置文件

```json
{
    "layout.layoutType": "POLAR",
    "appearance.backgroundColour": "#FAFAFA",
    "tipLabels.isShown": true,
    "tipLabels.fontName": "Arial",
    "tipLabels.fontSize": 10
}
```

```bash
figtreekit input.tre -o output.nex --config style.json
```

---

## Python API 参考

### 树样式

```python
from figtreekit import FigTreeStyler, LayoutType, FontStyle, TransformType

styler = FigTreeStyler("tree.nwk")

# 布局
styler.set_layout(LayoutType.POLAR)
styler.set_polar_layout(angular_range=270, root_angle=45)

# 外观
styler.set_appearance(background_color="#FFFFFF", branch_line_width=2.0)

# Clade 注解
styler.highlight_clade(["A", "B"], color="#FF0000")
styler.set_clade_color(["A", "B"], color="#2196F3")
styler.set_clade_color_all(["A", "B"], color="#2196F3")  # 子树全部分支着色
# 注意：set_clade_color + highlight_clade 作用于相同分类群时，
# MRCA 级别的颜色会被丢弃以避免 FigTree ClassCastException。
# 推荐使用 set_clade_color_all() 替代。
styler.set_clade_font(["A"], font_name="Arial", font_style=FontStyle.BOLD, font_size=14)
styler.set_clade_stroke(["A", "B"], stroke_width=2.0)

# 标签
styler.set_tip_labels(is_shown=True, font_size=12)
styler.set_node_labels(is_shown=True, display_attribute="height")
styler.set_branch_labels(is_shown=True, display_attribute="length")

# 比例尺
styler.set_scale_bar(is_shown=True)
styler.set_scale_axis(is_shown=True)
styler.set_scale(root_age=1.0)

# 布局专属设置
styler.set_radial_layout(spread=1.0)
styler.set_rectilinear_layout(curvature=0, root_length=0)

# 树属性
styler.set_trees(rooting=True, transform=TransformType.PHYLOGRAM)

# 图例 / 节点装饰
styler.set_legend(is_shown=True, position="bottom")
styler.set_node_bars(is_shown=True)
styler.set_node_shapes(is_shown=True)

# 从字典应用并重置
styler.apply_dict({"layout.layoutType": "POLAR"})

# 完全重置：清空设置、注解、分类学配置和树内容
# 重置后需重新 load_file / load_content 才能继续操作
styler.reset()

# 或者仅重置样式，保留已加载的树内容
styler.reset(keep_tree=True)

# 导出
styler.export("output.nex")
styler.render("tree.png")
styler.render("tree.pdf", format="PDF", width=1600, height=1000)
```

### 单系群与折叠

```python
# 检查单系性
result = styler.check_monophyly(["A", "B", "C"])
result = styler.check_monophyly_by_group("Cyanobacteriales")
result = styler.check_monophyly_by_group("LUCA")

# 折叠分支
styler.collapse_clade(["A", "B"], label="Clade1")
styler.collapse_by_group("Cyanobacteriales")
styler.collapse_by_group("Cyanobacteriales", label="Cyano")

# 嵌套折叠：同时折叠内外分支（自动按大小排序处理）
styler.collapse_clade(["A", "B"], label="Inner")
styler.collapse_clade(["A", "B", "C"], label="Outer")  # Inner 和 Outer 都会出现在输出中

# 便捷：检查并一次性设置样式
styler.style_monophyletic_clade(
    ["A", "B", "C"],
    color="#E91E63",
    highlight_color="#FFCDD2",
    font_name="Arial",
    font_style=FontStyle.BOLD,
    font_size=12,
)

# 清除待执行操作
styler.clear_annotations()
styler.clear_clade_hilights()
styler.clear_collapses()

# 移除树中所有括号注释（NHX、bootstrap、posterior 等），减小输出文件体积
styler.strip_annotations()

# 获取 clade 详细信息（MRCA、后代末端、单系性等）
info = styler.get_clade_info(["A", "B", "C"])
print(info["is_monophyletic"], info["mrca_terminal_count"])
```

### 加载与访问

```python
# 从字符串或文件加载（自动检测）
styler = FigTreeStyler().load_tree("((A:0.1,B:0.2):0.3,C:0.4);")
styler = FigTreeStyler().load_tree("tree.nwk")  # 如果文件存在，自动从文件加载

# 访问注解和折叠
annotations = styler.get_annotations()  # 获取当前注解列表
collapses = styler.get_collapses()      # 获取当前折叠列表

# 设置字体（使用默认参数）
styler.set_clade_font(["A", "B"])  # 使用默认值：Arial, PLAIN, 12
styler.set_clade_font(["A", "B"], font_name="Helvetica", font_style=FontStyle.BOLD, font_size=14)
```

### 验证

```python
from figtreekit import (
    validate_input_file,
    deep_validate_newick,
    deep_validate_fasta,
    deep_validate_fastq,
    TreeValidator,
)

# 文件验证
result = validate_input_file("tree.nwk")
if not result["valid"]:
    for err in result["errors"]:
        print(err)

# 深度 Newick 验证
dv = deep_validate_newick(content, label="tree.nwk")
for err in dv["errors"]:
    print(err)

# FASTA / FASTQ 验证
dv = deep_validate_fasta("seqs.fasta", expected_alphabet="DNA")
dv = deep_validate_fastq("reads.fastq", expected_alphabet="DNA")

# Styler 级别验证
issues = styler.validate()

# 生物学合理性检查（退化的树、全零分支、超大树警告）
warnings = TreeValidator.validate_biological_plausibility(newick)
```

### 分类学

```python
from figtreekit import (
    parse_taxonomy_auto,
    detect_taxonomy_format,
    TaxonomyMapper,
    MonophylyAnalyzer,
    get_rank_prefixes,
    extend_rank_prefixes,
)

# 从 CLI 参数应用设置
from figtreekit import apply_cli_args
# apply_cli_args(styler, args)  # args 来自 argparse.Namespace

# 自动检测并解析
tax = parse_taxonomy_auto("GB_GCA_000252485.1_d_Bacteria_p_Cyanobacteriota_c_Cyanobacteriia_o_Cyanobacteriales_f_Prochloraceae_g_Prochloron")
# {"domain": "Bacteria", "phylum": "Cyanobacteriota", ...}

tax = parse_taxonomy_auto("d__Archaea;p__Euryarchaeota;s__")
# {"domain": "Archaea", "phylum": "Euryarchaeota", "species": ""}

# Styler 分类学配置
styler.configure_taxonomy(
    delimiter_mode="reverse",      # reverse / greedy / segment
    table_sep=";",
    source_priority="table",       # table / embedded
    mapping_file="taxonomy.tsv",
    ignore_malformed=False,
)

# 直接使用映射器
mapper = TaxonomyMapper()
mapper.load_mapping("taxonomy.tsv")
groups = mapper.identify_groups(rank="genus")

# 分类学分析并自动识别单系群（需提供 pattern 或 mapping_file）
result = styler.analyze_taxonomy(mapping_file="taxonomy.tsv", rank="phylum")
# 便捷方法：等价于 analyze_taxonomy(mapping_file=...)
result = styler.analyze_taxonomy_from_mapping("taxonomy.tsv", rank="phylum")

# 从标签解析分类学（内置模式或自定义正则）
taxonomy = styler.parse_label_taxonomy("genus_species")

# 检查分类学数据完整性
completeness = styler.check_taxonomy_completeness(mapping_file="taxonomy.tsv")
```

### 库模式 API（Library Mode API）

```python
from figtreekit import (
    parse_taxonomy,        # 标准化分类学解析
    is_monophyletic,       # 单系群判定
    load_tree,             # 树加载
    cross_validate,        # 交叉验证
    # 标准化异常体系
    PhyloFormatError,      # 文件格式错误（继承自 ParseError）
    TaxonomyConflictError, # 分类学冲突（继承自 ValidationError）
    MonophylyError,        # 单系性分析错误（继承自 ValidationError）
)

# 解析分类学标签（标准化签名）
tax = parse_taxonomy("d__Bacteria;p__Cyanobacteriota", mode="reverse")
# -> {"domain": "Bacteria", "phylum": "Cyanobacteriota", ...}

# 判定单系群（标准化签名）
mono = is_monophyletic("tree.nwk", "Cyanobacteriota", rooted=True)
# -> True / False

# 加载树文件（标准化签名）
styler = load_tree("tree.nwk", validate=True)

# 交叉验证树与序列（标准化签名）
report = cross_validate("tree.nwk", "sequences.fasta", strict=True)
# -> {"valid": True, "matched": 50, "tree_only": [], "seq_only": [], "errors": []}
```

---

## 错误码

| 代码 | 含义 | 描述 |
|------|------|------|
| 0 | 成功 | 所有操作成功完成 |
| 1 | 运行时错误 | 依赖问题、自检失败 |
| 2 | 用法错误 | 无效命令行参数、缺少输入 |
| 3 | 数据错误 | 无效输入数据（格式错误的树、错误序列） |
| 130 | 中断 | 用户按 Ctrl+C（SIGINT）或收到 SIGTERM |

### 异常体系

| 异常类 | 基类 | 用途 |
|--------|------|------|
| `FigTreeKitError` | `Exception` | 所有 FigTreeKit 异常的基类 |
| `ParseError` | `FigTreeKitError` | 树/序列文件解析错误 |
| `ValidationError` | `FigTreeKitError` | 输入验证失败 |
| `ExportError` | `FigTreeKitError` | 导出/渲染错误 |
| `PhyloFormatError` | `ParseError` | 文件格式错误（库模式 API 别名） |
| `TaxonomyConflictError` | `ValidationError` | 分类学冲突（库模式 API 别名） |
| `MonophylyError` | `ValidationError` | 单系性分析错误（库模式 API 别名） |
| `CompatibilityWarning` | `UserWarning` | 兼容性警告 |

---

## 操作说明

### 输出控制

```bash
figtreekit tree.nwk -o existing.nex --force        # 覆盖
figtreekit tree.nwk -o existing.nex --no-clobber    # 存在时跳过
figtreekit tree.nwk -o new/dir/output.nex           # 自动创建目录
```

### 用户中断

按 `Ctrl+C` 优雅终止——显示进度，清理临时文件，退出码 130。

### 可移植性设计

- **编码**：UTF-8，带 BOM 和 latin-1 回退透明处理
- **换行符**：所有平台使用 Unix `\n`
- **路径**：全程使用 `pathlib.Path`（平台无关的路径处理）
- **临时文件**：退出时自动清理，权限设为 0o600（HPC 安全），包括 `Ctrl+C`

> **注意**：尽管代码使用了平台无关的设计模式，FigTreeKit 仅在 macOS Tahoe 26.5.2 上经过测试。不保证与 Windows 或 Linux 的兼容性。

---

## 大规模数据

超过 10,000 个末端的树：
- INFO 日志提示内存需求
- 使用 `--low-memory` 降低内存模式
- 安装 `psutil` 获取 DEBUG 级内存日志

### 资源估算

| 树大小 | 内存（约） | 解析时间 | 导出时间 |
|--------|-----------|---------|---------|
| 100 末端 | < 10 MB | < 0.01 s | < 0.01 s |
| 1,000 末端 | ~ 20 MB | < 0.01 s | ~ 0.01 s |
| 10,000 末端 | ~ 100 MB | ~ 0.01 s | ~ 0.1 s |
| 100,000 末端 | ~ 1 GB | ~ 0.1 s | ~ 1 s |

---

## FigTree 渲染设置

> **替代方案提示**：FigTreeKit 的渲染依赖 FigTree JAR，目的是在自动化流程中保留 FigTree 注解与样式。如果你只需要一个**跨平台 GUI/CLI 工具直接渲染超大规模树**（>100,000 taxa），而不需要 FigTree 兼容的 Nexus 注解，可以考虑 [TreeViewer](https://doi.org/10.1002/ece3.10873)。

### 检查状态

```bash
figtreekit --check-figtree
```

### 下载并编译

```bash
figtreekit --setup-figtree
```

### 使用已有 JAR

```bash
figtreekit --setup-figtree --figtree-jar /path/to/figtree.jar
```

### 渲染输出格式

| 格式 | 扩展名 | 适用场景 |
|------|--------|---------|
| PNG | `.png` | 网页、演示、快速预览 |
| PDF | `.pdf` | 出版、矢量编辑 |
| SVG | `.svg` | 网页、可缩放矢量图形 |
| JPEG | `.jpg` | 邮件、小文件大小 |

```bash
# PNG（默认，适合大多数场景）
figtreekit tree.nwk -o tree.nex --render tree.png

# PDF 用于出版
figtreekit tree.nwk -o tree.nex --render tree.pdf

# SVG 用于网页
figtreekit tree.nwk -o tree.nex --render tree.svg

# 自定义尺寸
figtreekit tree.nwk -o tree.nex --render tree.png --render-width 2000 --render-height 1500

# 显式指定渲染格式（当扩展名不清晰时）
figtreekit tree.nwk -o tree.nex --render tree.out --render-format PNG
```

详见 [docs/user_manual_CN.md](docs/user_manual_CN.md) 了解详细编译说明。

---

## 联系方式与维护者

- **作者**：曾子超（上海交通大学）
- **邮箱**：zengzichao@sjtu.edu.cn
- **GitHub Issues**：https://github.com/ZengZichao/FigTreeKit/issues
- **GitHub Discussions**：https://github.com/ZengZichao/FigTreeKit/discussions

---

## 引用

如果您在研究中使用 FigTreeKit，请引用：

```bibtex
@software{figtreekit2026,
  author = {Zeng, Zichao},
  title = {FigTreeKit: Programmatic styling of phylogenetic trees for FigTree visualization},
  year = {2026},
  url = {https://github.com/ZengZichao/FigTreeKit}
}
```

---

## 许可证

FigTreeKit 是根据 **GNU 通用公共许可证第 2 版或更高版本（GPL-2.0-or-later）** 授权的自由软件。

本程序按“原样”提供，不附带任何明示或默示担保，包括但不限于对适销性或特定用途适用性的担保。详情请参见 [LICENSE](LICENSE) 文件。

### 第三方组件

- **FigTree**（`figtreekit/figtree_patched.jar`、`_figtree_patch/`、修改后的 Java 源码位于 `_figtree_patch/src/figtree/`）：衍生自 Andrew Rambaut 的 [FigTree v1.4.4](http://tree.bio.ed.ac.uk/software/figtree/)，授权为 GPL-2.0-or-later。原始未修改 JAR（`_figtree_patch/figtree_original.jar`）亦一并提供以满足 GPL 源代码提供要求；重建方法见 `_figtree_patch/README.md`。
- **iText**（打包在 FigTree JAR 中用于 PDF 导出）：授权为 GNU Affero 通用公共许可证第 3 版（AGPL-3.0）。
- **Biopython**（运行时依赖）：BSD-3-Clause。

当你再分发 FigTreeKit 或打过补丁的 FigTree JAR 时，须遵守 GPL-2.0-or-later 与 AGPL-3.0 的 copyleft 条款。

**许可证兼容性说明**：FigTreeKit 采用 GPL-2.0-**or-later**（允许升级到后续版本 GPL-3.0），从而与 iText 的 AGPL-3.0 实现兼容。GPL-3.0 与 AGPL-3.0 之间存在明确的兼容性路径（AGPL-3.0 §13）。下游用户若需在严格合规环境中使用，可将 FigTreeKit 整体视作 GPL-3.0/AGPL-3.0 组合许可项目。

---

## 链接

- **代码仓库**：https://github.com/ZengZichao/FigTreeKit
- **PyPI**：https://pypi.org/project/figtreekit/
- **Zenodo 归档**：[![DOI](https://zenodo.org/badge/latestdoi/https://github.com/ZengZichao/FigTreeKit.svg)](https://zenodo.org/badge/latestdoi/https://github.com/ZengZichao/FigTreeKit)（每次 GitHub Release 自动生成，详见 [.zenodo.json](.zenodo.json)）
- **文档**：[docs/user_manual_CN.md](docs/user_manual_CN.md)
- **FigTree**：http://tree.bio.ed.ac.uk/software/figtree/
- **TreeViewer**：https://doi.org/10.1002/ece3.10873
- **Biopython**：https://biopython.org/

---

## 测试环境

本软件仅在以下环境中开发并测试：

| 操作系统 | Python | Biopython | 状态 |
|---------|--------|-----------|------|
| macOS Tahoe 26.5.2（Apple Silicon） | 3.11 | 1.88 | ✅ 通过 |

> **注意**：FigTreeKit 仅在 macOS Tahoe 26.5.2 + Python 3.11 环境下开发并测试。未验证与其他操作系统（Windows、Linux）或 Python 版本的兼容性。

复现环境：
```bash
pip install figtreekit==1.0.1 biopython==1.88
figtreekit --self-test
```

---

## 贡献

欢迎贡献！请参阅 [CONTRIBUTING.md](https://github.com/ZengZichao/FigTreeKit/blob/main/CONTRIBUTING.md) 了解指南。

