# FigTreeKit 用户手册

**版本**: 1.0.0 | **许可证**: GPL-2.0-or-later | **Python**: 3.11 | **平台**: macOS Tahoe 26.5.2

FigTreeKit 是一个用于系统发育树 FigTree 可视化样式编程的 Python 库。它生成兼容 FigTree 的 Nexus 文件，完整支持 `[&!hilight]`、`[&!color]`、`[&!font]` 注解，支持分类学感知的分支折叠，并集成命令行图片渲染功能。

---

## 1. 安装

### 从 PyPI 安装（推荐）

```bash
pip install figtreekit
```

### 从源码安装

```bash
git clone https://github.com/ZengZichao/FigTreeKit.git
cd FigTreeKit
pip install -e .
```

### 依赖项

| 包 | 版本 | 必需 | 用途 |
|---|------|------|------|
| biopython | >=1.80, <2.0 | 是 | 树解析（Bio.Phylo）；bracket-comment 保留依赖 ≥1.80 |
| psutil | 任意 | 否 | 内存日志 |
| tqdm | 任意 | 否 | 进度条（批量模式） |
| Java 8+ | 任意 | 否 | 通过 FigTree JAR 渲染图片 |

### 验证安装

```bash
figtreekit --self-test
figtreekit --version
```

---

## 2. 输入格式

### 树文件

| 格式 | 扩展名 | 描述 |
|------|--------|------|
| Newick | `.nwk`, `.newick`, `.tree`, `.tre`, `.treefile`, `.nh`, `.nhy`, `.nhx` | 标准系统发育树格式 |
| Nexus | `.nex`, `.nexus`, `.nx` | 带元数据块的扩展格式 |
| PhyloXML | `.xml`, `.phyloxml` | 基于 XML 的系统发育格式 |

### 序列文件（用于交叉验证）

| 格式 | 扩展名 |
|------|--------|
| FASTA | `.fasta`, `.fa`, `.fas`, `.fna`, `.faa`, `.ffn`, `.frn` |
| FASTQ | `.fastq`, `.fq` |
| GenBank | `.gb`, `.gbk`, `.genbank` |
| EMBL | `.embl` |
| Stockholm | `.stockholm`, `.sto` |
| Phylip | `.phylip`, `.phy` |
| Clustal | `.clustal`, `.aln` |

### 分类学映射文件

两列 TSV/CSV 格式（自动检测），可带或不带表头：

```
name	taxonomy
GB_GCA_000252485.1	d__Bacteria;p__Cyanobacteriota;c__Cyanobacteriia;o__Cyanobacteriales;f__Prochloraceae;g__Prochloron;s__
```

---

## 3. 命令行接口 — 完整参考

### 命令格式

```
figtreekit [input] [-o OUTPUT] [OPTIONS]
```

`input` 可以是单个树文件或目录（批量模式）。

### 3.1 通用选项

| 选项 | 描述 |
|------|------|
| `-h`, `--help` | 显示帮助信息并退出 |
| `--version` | 显示版本号、git hash 与构建日期 |
| `--self-test` | 运行内置诊断检查（11 项测试） |
| `-v` | 详细输出（DEBUG 级日志） |
| `-q` | 安静模式（抑制 INFO 消息） |
| `-o OUTPUT` | 输出 Nexus 文件路径（批量模式下为目录） |
| `--validate` | 仅验证输入文件（不生成输出） |
| `--config FILE` | JSON 配置文件（见第 5 节） |
| `--log-file FILE` | 将日志输出写入文件 |
| `--force` | 覆盖已存在的输出文件 |
| `--no-clobber` | 绝不覆盖已存在的输出（存在则报错） |
| `--strip-annotations` | 移除括号注释（NHX/bootstrap/posterior）以减小文件体积 |
| `--low-memory` | 低内存模式（适用于 >10k 末端的大树） |

### 3.2 布局选项

| 选项 | 取值 | 默认值 | 描述 |
|------|------|--------|------|
| `--layout` | `rectilinear`, `polar`, `radial` | `rectilinear` | 树布局类型 |
| `--expansion INT` | >= 0 | — | 布局扩展值 |
| `--zoom FLOAT` | > 0 | — | 布局缩放因子 |

### 3.3 外观选项

| 选项 | 描述 |
|------|------|
| `--branch-width FLOAT` | 分支线宽 |
| `--branch-color-attribute ATTR` | 分支着色所用属性 |
| `--background-color #RRGGBB` | 背景颜色 |
| `--foreground-color #RRGGBB` | 前景（分支）颜色 |
| `--selection-color #RRGGBB` | 选择高亮颜色 |

### 3.4 树根性与变换

| 选项 | 描述 |
|------|------|
| `--rooted` | 显示为有根树 |
| `--unrooted` | 显示为无根树 |
| `--rooting-type {user,midpoint}` | 定根方法（用户选择 / 中点法） |
| `--transform {cladogram,phylogram}` | 变换类型：cladogram（等长分支）/ phylogram（按比例） |
| `--order {increasing,decreasing}` | 按节点密度排序分支 |
| `--order-branches` | 启用分支排序（递增节点密度） |

### 3.5 末端标签

| 选项 | 描述 |
|------|------|
| `--tip-labels-show` | 显示末端标签 |
| `--tip-labels-hide` | 隐藏末端标签 |
| `--font-name NAME` | 字体族名（如 "Arial"） |
| `--font-size PT` | 字号（磅，> 0） |
| `--font-style 0-3` | 0=常规, 1=粗体, 2=斜体, 3=粗斜体 |
| `--label-color #RRGGBB` | 末端标签颜色 |

### 3.6 节点标签

| 选项 | 描述 |
|------|------|
| `--node-labels-show` | 显示节点标签 |
| `--node-labels-hide` | 隐藏节点标签 |
| `--node-display-attribute ATTR` | 显示的属性（如 "height", "support"） |

### 3.7 分支标签

| 选项 | 描述 |
|------|------|
| `--branch-labels-show` | 显示分支标签 |
| `--branch-labels-hide` | 隐藏分支标签 |
| `--branch-display-attribute ATTR` | 显示的属性（如 "length", "posterior"） |

### 3.8 比例尺与刻度轴

| 选项 | 描述 |
|------|------|
| `--scale-bar-show` | 显示比例尺 |
| `--scale-bar-hide` | 隐藏比例尺 |
| `--scale-axis-show` | 显示刻度轴（时间轴） |
| `--scale-axis-hide` | 隐藏刻度轴 |
| `--root-age FLOAT` | 根年龄（>= 0） |
| `--scale-factor FLOAT` | 缩放因子（> 0） |

### 3.9 极坐标布局

| 选项 | 描述 |
|------|------|
| `--angular-range DEG` | 角度范围（0–360°，默认 360） |
| `--root-angle DEG` | 根角度（0–360°） |
| `--align-tip-labels` | 径向对齐末端标签 |

### 3.10 放射状布局

| 选项 | 描述 |
|------|------|
| `--radial-spread FLOAT` | 放射展开因子（>= 0） |

### 3.11 矩形树布局

| 选项 | 描述 |
|------|------|
| `--curvature INT` | 分支曲率（>= 0） |
| `--root-length INT` | 根分支长度（像素，>= 0） |

### 3.12 图例

| 选项 | 描述 |
|------|------|
| `--legend-show` | 显示图例 |
| `--legend-position {top,bottom,left,right}` | 图例位置（默认 bottom） |

### 3.13 分支折叠

| 选项 | 描述 |
|------|------|
| `--clade NAME` | 按分类群名称折叠分支。先检查单系性；非单系则警告并跳过（配合 `--strict` 则终止）。可重复指定。 |
| `--strict` | 遇到非单系群时终止（而非跳过） |
| `--collapse-taxa TAXA` | 按指定分类单元名折叠（逗号分隔）。支持 `label=NAME` 和 `type=TYPE` 标记。可重复指定。 |
| `--collapse-rank RANK` | 折叠指定分类级别的**所有**单系群（如 `phylum`, `class`）。需要分类学信息。 |
| `--collapse-style {collapse,cartoon}` | 折叠样式：`collapse`（三角+标签）/ `cartoon`（三角保留分支跨度）。默认 `collapse`。 |

**`--collapse-taxa` 格式示例：**

```bash
# 基本用法：逗号分隔的分类单元名
--collapse-taxa "TaxonA,TaxonB,TaxonC"

# 带显式标签和类型
--collapse-taxa "TaxonA,TaxonB,label=MyClade,type=cartoon"
```

### 3.14 分支着色与高亮

| 选项 | 描述 |
|------|------|
| `--auto-color [RANK]` | 自动为指定级别的所有单系群分配颜色（默认 phylum）。可重复。 |
| `--highlight SPEC` | 高亮分支。格式：`"A,B,C[:#RRGGBB[:width[:offset]]]"`。可重复。 |
| `--color-clade SPEC` | 着色分支（仅 MRCA 分支）。格式：`"A,B,C:#RRGGBB"`。可重复。 |
| `--color-all` | 配合 `--color-clade` 使用，着色**所有**后代分支（set_clade_color_all） |
| `--font-clade SPEC` | 设置分支字体。格式：`"A,B,C:FONTNAME[-STYLE[-SIZE]]"`。可重复。 |
| `--clear-hilights` | 清除所有高亮注解 |

**示例：**

```bash
# 自动为门级类群着色
figtreekit tree.nwk -o out.nex --auto-color phylum

# 自定义颜色和宽度的高亮
figtreekit tree.nwk -o out.nex --highlight "A,B,C:#FF0000:6:2"

# 着色某分支的所有后代
figtreekit tree.nwk -o out.nex --color-clade "A,B,C:#2196F3" --color-all

# 设置粗体字体
figtreekit tree.nwk -o out.nex --font-clade "A,B,C:Arial-BOLD-14"
```

### 3.15 分类学分析

| 选项 | 描述 |
|------|------|
| `--taxonomy-levels SPEC` | 自定义等级前缀映射（如 `"d:domain,sp:superphylum,p:phylum,c:class,o:order,f:family,g:genus"`） |
| `--taxonomy-delimiter-mode {reverse,greedy,segment}` | 分类学解析模式 |
| `--taxonomy-table-sep CHAR` | 表格式分类学的分隔符（格式 B） |
| `--taxonomy-source-priority {embedded,table}` | 两种格式并存时的优先级 |
| `--taxonomy-mapping-file FILE` | 外部分类学映射文件（TSV/CSV） |
| `--table-sep CHAR` | `--taxonomy-table-sep` 的别名 |
| `--ignore-malformed` | 跳过解析失败的标签 |
| `--analyze-taxonomy [RANK]` | 打印单系群报告并退出（默认级别：phylum） |
| `--check-monophyly NAME` | 检查指定群是否为单系群。支持特殊标识符：LUCA/LACA/LBCA/root。可重复。 |
| `--check-taxonomy` | 检查所有末端的分类学完整性并退出 |

### 3.16 多树处理

| 选项 | 描述 |
|------|------|
| `--multi-tree MODE` | 策略：`split`, `first`, `last`, `random`, `all`（= split）, `ask`（默认） |
| `--seed N` | `--multi-tree random` 的随机种子 |

### 3.17 序列交叉验证

| 选项 | 描述 |
|------|------|
| `--sequences FILE` | 用于与树末端交叉验证的序列文件 |
| `--mol-type {DNA,RNA,protein}` | 验证时的预期分子类型 |
| `--no-cross-check` | 跳过树-序列交叉验证 |
| `--skip-length-check` | 跳过序列长度一致性检查 |

### 3.18 渲染

| 选项 | 描述 |
|------|------|
| `--render FILE` | 渲染输出为图片文件（按扩展名判断格式） |
| `--render-format {PNG,PDF,SVG,JPEG}` | 显式指定渲染格式（覆盖扩展名检测） |
| `--render-width PX` | 渲染宽度（像素，默认 1200） |
| `--render-height PX` | 渲染高度（像素，默认 800） |

### 3.19 FigTree 设置

| 选项 | 描述 |
|------|------|
| `--setup-figtree` | 下载 FigTree v1.4.4 源码、应用补丁并编译 |
| `--check-figtree` | 检查 FigTree JAR 可用性和状态 |
| `--figtree-jar PATH` | 指定已有的 FigTree JAR 路径 |

### 3.20 高级：任意 FigTree 参数

| 选项 | 描述 |
|------|------|
| `--set KEY=VALUE` | 直接设置任意 FigTree 参数。可重复指定。 |

**示例：**

```bash
figtreekit tree.nwk -o out.nex --set tipLabels.fontSize=8
figtreekit tree.nwk -o out.nex --set polarLayout.angularRange=180000
figtreekit tree.nwk -o out.nex --set scaleAxis.reverseAxis=true
figtreekit tree.nwk -o out.nex --set scaleAxis.significantDigits=2
figtreekit tree.nwk -o out.nex --set appearance.branchLineWidth=2.5
```

键名遵循 FigTree 内部参数命名规范（如 `tipLabels.*`、`nodeLabels.*`、`scaleAxis.*`、`polarLayout.*`、`rectilinearLayout.*`、`appearance.*`）。

---

## 4. Python API — 完整参考

### 4.1 FigTreeStyler 类

所有树样式操作的核心类。所有设置方法返回 `self`，支持方法链式调用。

```python
from figtreekit import FigTreeStyler, LayoutType, FontStyle

styler = FigTreeStyler("tree.nwk")  # 从文件加载
styler = FigTreeStyler()            # 空实例，稍后加载
```

#### 加载树

| 方法 | 描述 |
|------|------|
| `load_tree(source)` | 自动检测文件路径或内联 Newick/Nexus 内容 |
| `load_file(file_path, encoding=None)` | 从文件加载（可指定编码） |
| `load_content(content)` | 从字符串内容加载 |
| `get_tree_content()` | 返回原始树内容字符串 |
| `parse_tree()` | 返回 Bio.Phylo 树对象 |
| `reset(keep_tree=False)` | 重置所有注解、设置和分类学配置。`keep_tree=True` 时保留已加载的树内容 |

#### 布局配置

| 方法 | 参数 | 描述 |
|------|------|------|
| `set_layout(layout_type, expansion=None, zoom=None)` | `LayoutType.RECTILINEAR/POLAR/RADIAL` | 设置树布局 |
| `set_polar_layout(**kwargs)` | `angular_range`, `root_angle` | 极坐标专用设置 |
| `set_radial_layout(**kwargs)` | `spread` | 放射状专用设置 |
| `set_rectilinear_layout(**kwargs)` | `curvature`, `root_length` | 矩形树专用设置 |

#### 外观

| 方法 | 参数 | 描述 |
|------|------|------|
| `set_appearance(**kwargs)` | `background_color`, `foreground_color`, `branch_line_width`, `selection_color` | 全局外观 |
| `set_hilighting(is_shown=None, gradient=None)` | — | 切换高亮显示 |

#### 标签

| 方法 | 参数 | 描述 |
|------|------|------|
| `set_tip_labels(**kwargs)` | `is_shown`, `font_name`, `font_size`, `font_style`, `color`, `align` | 末端标签设置 |
| `set_node_labels(**kwargs)` | `is_shown`, `display_attribute`, `font_name`, `font_size` | 节点标签设置 |
| `set_branch_labels(**kwargs)` | `is_shown`, `display_attribute`, `font_name`, `font_size` | 分支标签设置 |
| `set_align_tip_labels(align=True)` | — | 径向对齐末端标签 |

#### 比例尺

| 方法 | 参数 | 描述 |
|------|------|------|
| `set_scale_bar(**kwargs)` | `is_shown`, `font_size` | 比例尺设置 |
| `set_scale_axis(**kwargs)` | `is_shown`, `automatic_scale`, `reverse_axis`, `show_grid`, `font_size`, `significant_digits` | 刻度轴（时间轴） |
| `set_scale(**kwargs)` | `root_age`, `scale_factor` | 缩放参数 |

#### 图例

| 方法 | 参数 | 描述 |
|------|------|------|
| `set_legend(**kwargs)` | `is_shown`, `position` | 图例设置 |

#### 树属性

| 方法 | 参数 | 描述 |
|------|------|------|
| `set_trees(rooting, rooting_type, transform, transform_type, order, order_type)` | 见枚举类型 | 根性、变换、排序 |

#### 分支注解

| 方法 | 描述 |
|------|------|
| `highlight_clade(taxon_names, color="#804548", width=4, offset=0.0)` | 添加 `[&!hilight]` 注解 |
| `set_clade_color(taxon_names, color)` | 仅对 MRCA 分支添加 `[&!color]` |
| `set_clade_color_all(taxon_names, color)` | 对**所有**后代分支添加 `[&!color]` |
| `set_clade_font(taxon_names, font_name, font_style, font_size)` | 添加 `[&!font]` 注解 |
| `set_clade_stroke(taxon_names, stroke_width)` | 设置分支线宽 |
| `set_clade_hilight(clade_identifier, tip_count, height, color)` | 底层高亮注入 |
| `style_monophyletic_clade(taxon_names, color, highlight_color, ...)` | 组合着色+高亮+字体（用于单系群） |
| `clear_clade_hilights()` | 移除所有高亮注解 |
| `clear_annotations()` | 移除**所有**注解 |

#### 分支折叠

| 方法 | 描述 |
|------|------|
| `collapse_clade(taxon_names, label=None, collapse_type="collapse")` | 按分类单元名折叠 |
| `cartoon_clade(taxon_names, label=None)` | 以 cartoon 样式折叠 |
| `collapse_by_group(group_name, pattern=None, mapping_file=None, label=None, collapse_type="collapse")` | 按分类群名称折叠 |
| `clear_collapses()` | 移除所有折叠注解 |
| `get_collapses()` | 返回当前折叠列表 |

#### 分类学分析

| 方法 | 描述 |
|------|------|
| `configure_taxonomy(delimiter_mode, table_sep, source_priority, mapping_file, ignore_malformed, file_delimiter)` | 配置分类学解析 |
| `parse_label_taxonomy(pattern)` | 用正则表达式解析所有标签 |
| `analyze_taxonomy(pattern, mapping_file, rank, style_monophyletic, color, highlight_color)` | 完整分类学分析（含单系群检测） |
| `analyze_taxonomy_from_mapping(mapping_file, rank, style_monophyletic)` | 从外部映射文件分析 |
| `check_monophyly(taxon_names)` | 检查指定分类单元是否构成单系群 |
| `check_monophyly_by_group(group_name, pattern, mapping_file)` | 按群名检查单系性 |
| `check_taxonomy_completeness(pattern, mapping_file, required_ranks)` | 报告缺失的分类学数据 |

#### 验证与导出

| 方法 | 描述 |
|------|------|
| `validate()` | 运行结构验证，返回问题列表 |
| `get_clade_info(taxon_names)` | 获取指定分类单元的 MRCA 信息 |
| `get_annotations()` | 返回所有节点注解 |
| `get_settings()` | 返回当前 FigTree 设置字典 |
| `apply_dict(settings_dict)` | 从字典应用设置 |
| `set_custom_param(key, value)` | 设置任意 FigTree 参数 |
| `strip_annotations()` | 移除树内容中的括号注释 |
| `export(output_file, include_taxa_block=True, single_tree=False)` | 导出为 Nexus 文件 |
| `render(output_file, format=None, width=1200, height=800, jar_path=None, keep_nex=False)` | 通过 FigTree JAR 渲染为图片 |

### 4.2 枚举类型

```python
from figtreekit import LayoutType, FontStyle
from figtreekit.enums import RootingType, TransformType, OrderType
```

| 枚举 | 取值 |
|------|------|
| `LayoutType` | `RECTILINEAR`, `POLAR`, `RADIAL` |
| `FontStyle` | `PLAIN` (0), `BOLD` (1), `ITALIC` (2), `BOLD_ITALIC` (3) |
| `RootingType` | `USER_SELECTION`, `MID_POINT` |
| `TransformType` | `CLADOGRAM`, `PHYLOGRAM` |
| `OrderType` | `INCREASING_NODE_DENSITY`, `DECREASING_NODE_DENSITY` |

### 4.3 库模式 API

用于流水线集成（Snakemake/Nextflow）的标准化函数：

```python
from figtreekit import (
    parse_taxonomy,         # parse_taxonomy(label, mode="reverse")
    parse_taxonomy_auto,    # 自动检测格式
    detect_taxonomy_format, # 检测格式 A 或 B
    is_monophyletic,        # is_monophyletic(tree, group_name, rooted=True)
    load_tree,              # load_tree(path, validate=True)
    cross_validate,         # cross_validate(tree_path, seq_path, strict=True)
    validate_input_file,    # validate_input_file(path)
    deep_validate_newick,   # deep_validate_newick(content, label="")
    deep_validate_fasta,    # deep_validate_fasta(path, expected_alphabet=None)
    apply_cli_args,         # apply_cli_args(styler, args)
)
```

### 4.4 异常体系

| 异常类 | 基类 | 用途 |
|--------|------|------|
| `FigTreeKitError` | `Exception` | 所有 FigTreeKit 异常的基类 |
| `ParseError` | `FigTreeKitError` | 树/序列文件解析错误 |
| `ValidationError` | `FigTreeKitError` | 输入验证失败 |
| `ExportError` | `FigTreeKitError` | 导出/渲染错误 |
| `PhyloFormatError` | `ParseError` | 文件格式错误（库模式 API 别名） |
| `TaxonomyConflictError` | `ValidationError` | 分类学冲突（库模式 API 别名） |
| `MonophylyError` | `ValidationError` | 单系性分析错误（库模式 API 别名） |
| `CompatibilityWarning` | `UserWarning` | FigTree 兼容性警告 |

---

## 5. 配置文件（JSON）

通过 JSON 文件批量应用 FigTree 设置：

```json
{
    "layout.layoutType": "POLAR",
    "appearance.backgroundColour": "#FAFAFA",
    "appearance.branchLineWidth": 2.0,
    "tipLabels.isShown": true,
    "tipLabels.fontName": "Arial",
    "tipLabels.fontSize": 10,
    "nodeLabels.isShown": false,
    "scaleAxis.isShown": true,
    "scaleAxis.reverseAxis": true,
    "polarLayout.angularRange": 180000,
    "polarLayout.rootAngle": 90000
}
```

```bash
figtreekit input.tre -o output.nex --config style.json
```

---

## 6. 渲染

FigTreeKit 内置基于 FigTree v1.4.4 修改的 JAR，支持无头渲染。PyPI 安装包已包含预编译 JAR，通常无需额外设置。

### 支持的输出格式

| 格式 | 扩展名 | 适用场景 |
|------|--------|----------|
| PNG | `.png` | 网页、演示、快速预览 |
| PDF | `.pdf` | 出版、矢量编辑 |
| SVG | `.svg` | 网页、可缩放矢量图形 |
| JPEG | `.jpg` | 小文件体积（有损压缩） |

### CLI 渲染

```bash
figtreekit input.tre -o out.nex --render tree.png
figtreekit input.tre -o out.nex --render tree.pdf --render-width 2400 --render-height 1600
```

### API 渲染

```python
styler.render("tree.png", format="PNG", width=2400, height=1600)
styler.render("tree.pdf", format="PDF", width=2400, height=1600)
```

### 重新编译 FigTree JAR（从源码）

```bash
figtreekit --setup-figtree
figtreekit --check-figtree
figtreekit --setup-figtree --figtree-jar /path/to/figtree.jar
```

---

## 7. 分类学分析工作流

FigTreeKit 支持两种分类学标签格式：

- **格式 A（嵌入式）**：`GCA_001_d__Archaea_p__Euryarchaeota_c__Methanobacteria_...`
- **格式 B（表格式）**：`d__Archaea;p__Euryarchaeota;c__Methanobacteria;...`

### 完整 CLI 工作流

```bash
# 1. 检查分类学完整性
figtreekit tree.nwk --check-taxonomy --taxonomy-levels "d:domain,p:phylum,c:class,o:order,f:family,g:genus"

# 2. 分析门级单系群
figtreekit tree.nwk --analyze-taxonomy phylum --taxonomy-levels "d:domain,p:phylum,c:class"

# 3. 检查特定群
figtreekit tree.nwk --check-monophyly Cyanobacteriota

# 4. 自动着色 + 折叠 + 导出 + 渲染
figtreekit tree.nwk -o out.nex \
  --taxonomy-levels "d:domain,sp:superphylum,p:phylum,c:class,o:order,f:family,g:genus" \
  --layout polar --auto-color phylum \
  --collapse-rank class --collapse-style cartoon \
  --tip-labels-hide \
  --set polarLayout.angularRange=180000 --set polarLayout.rootAngle=90000 \
  --render out.png --render-width 2400 --render-height 1600 --force
```

### 完整 API 工作流

```python
from figtreekit import FigTreeStyler, LayoutType
from figtreekit.taxonomy import TaxonomyMapper, MonophylyAnalyzer
from figtreekit._renderer import render_with_figtree

# 加载并配置
styler = FigTreeStyler("tree.nwk")
styler.set_layout(LayoutType.POLAR)
styler.set_tip_labels(is_shown=False)
styler.set_polar_layout(angular_range=180, root_angle=270)
styler.set_scale_axis(is_shown=True, reverse_axis=False, font_size=14, significant_digits=2)

# 分类学驱动着色
styler.analyze_taxonomy(mapping_file="taxonomy.tsv", rank="phylum",
                        style_monophyletic=True, color="#E91E63")

# 纲级折叠
styler.collapse_by_group("Methanobacteria", collapse_type="cartoon")

# 导出并渲染
styler.export("output.nex")
render_with_figtree("output.nex", "output.png", format="PNG", width=2400, height=1600)
```

---

## 8. 批量处理

处理目录中的所有树文件：

```bash
figtreekit trees_dir/ -o output_dir/ --layout polar --config style.json --force
```

---

## 9. 退出码

| 代码 | 含义 | 描述 |
|------|------|------|
| 0 | 成功 | 所有操作成功完成 |
| 1 | 运行时错误 | 依赖问题、自检失败、意外错误 |
| 2 | 用法错误 | 无效命令行参数、缺少输入 |
| 3 | 数据错误 | 无效输入数据（格式错误的树、错误序列） |
| 130 | 中断 | 用户按 Ctrl+C（SIGINT）或收到 SIGTERM |

---

## 10. 故障排除

| 问题 | 解决方案 |
|------|----------|
| "File not found" | 确保输入路径存在且是常规文件 |
| "Multiple trees detected" | 使用 `--multi-tree first/split/last/random` |
| "Non-monophyletic group" 警告 | 使用 `--strict` 终止，或折叠被跳过 |
| "Negative branch length" | 处理前修复树 |
| "Duplicate tip name" | 确保所有末端名唯一 |
| "Control character detected" | 清理输入文件中的恶意字符 |
| "Tree-sequence cross-validation FAILED" | 使用 `--no-cross-check` 或修复标签不匹配 |
| 大树处理缓慢 | 使用 `--low-memory`；>50k 末端需 2–4 GB 内存 |
| FigTree JAR 未找到 | 运行 `figtreekit --setup-figtree` 或设置 `--figtree-jar` |
| FigTree 中 `ClassCastException` | 避免对相同分类群同时使用 `set_clade_color` + `highlight_clade`；改用 `set_clade_color_all` |

---

## 11. FigTree 参数参考（--set 键名）

`--set KEY=VALUE` 常用键名：

| 键名 | 类型 | 描述 |
|------|------|------|
| `tipLabels.isShown` | bool | 显示/隐藏末端标签 |
| `tipLabels.fontName` | string | 末端标签字体族 |
| `tipLabels.fontSize` | int | 末端标签字号 |
| `tipLabels.fontStyle` | int | 0=常规, 1=粗体, 2=斜体, 3=粗斜体 |
| `tipLabels.color` | color | 末端标签颜色 |
| `nodeLabels.isShown` | bool | 显示/隐藏节点标签 |
| `nodeLabels.displayAttribute` | string | 节点标签属性 |
| `branchLabels.isShown` | bool | 显示/隐藏分支标签 |
| `appearance.branchLineWidth` | float | 分支线宽 |
| `appearance.backgroundColour` | color | 背景颜色 |
| `layout.layoutType` | string | RECTILINEAR / POLAR / RADIAL |
| `layout.expansion` | int | 布局扩展 |
| `layout.zoom` | float | 布局缩放 |
| `polarLayout.angularRange` | int | 角度范围（×1000，如 180000 = 180°） |
| `polarLayout.rootAngle` | int | 根角度（×1000） |
| `rectilinearLayout.curvature` | int | 分支曲率 |
| `rectilinearLayout.rootLength` | int | 根长度（像素） |
| `scaleAxis.isShown` | bool | 显示/隐藏刻度轴 |
| `scaleAxis.reverseAxis` | bool | 反转轴方向 |
| `scaleAxis.fontSize` | int | 轴字号 |
| `scaleAxis.significantDigits` | int | 有效数字位数 |
| `scaleBar.isShown` | bool | 显示/隐藏比例尺 |
| `legend.isShown` | bool | 显示/隐藏图例 |
| `trees.rooting` | bool | 有根/无根 |
| `trees.transform` | bool | 启用变换 |
| `trees.transformType` | string | cladogram / phylogram |
| `trees.order` | bool | 启用分支排序 |
| `trees.orderType` | string | Increasing/Decreasing Node Density |

> **注意**：极坐标角度使用 FigTree 内部的 ×1000 表示。`--set polarLayout.angularRange=180000` 等于 180°。Python API 的 `set_polar_layout(angular_range=180)` 直接接受角度值。
# FigTreeKit 用户手册

## 安装

```bash
pip install figtreekit
```

验证安装：
```bash
figtreekit --self-test
```

## 输入格式

### 树文件

| 格式 | 扩展名 | 描述 |
|------|--------|------|
| Newick | `.nwk`, `.newick`, `.tree`, `.tre`, `.treefile`, `.nh`, `.nhy`, `.nhx` | 标准系统发育树格式 |
| Nexus | `.nex`, `.nexus`, `.nx` | 带元数据块的扩展格式 |
| PhyloXML | `.xml`, `.phyloxml` | 基于 XML 的系统发育格式 |

### 序列文件

| 格式 | 扩展名 | 描述 |
|------|--------|------|
| FASTA | `.fasta`, `.fa`, `.fas`, `.fna`, `.faa`, `.ffn`, `.frn` | 标准序列格式 |
| FASTQ | `.fastq`, `.fq` | 带质量值的测序 reads |
| GenBank | `.gb`, `.gbk`, `.genbank` | GenBank 注释格式 |
| EMBL | `.embl` | EMBL 序列格式 |
| Stockholm | `.stockholm`, `.sto` | 多序列比对格式 |
| Phylip | `.phylip`, `.phy` | Phylip 比对格式 |
| Clustal | `.clustal`, `.aln` | Clustal 比对格式 |

### 分类学映射文件

两列 TSV/CSV 格式（自动检测）：

有表头：
```
name	taxonomy
GB_GCA_000252485.1	d__Bacteria;p__Cyanobacteriota;c__Cyanobacteriia;o__Cyanobacteriales;f__Prochloraceae;g__Prochloron;s__
```

无表头：
```
GB_GCA_000252485.1	d__Bacteria;p__Cyanobacteriota;c__Cyanobacteriia;o__Cyanobacteriales;f__Prochloraceae;g__Prochloron;s__
```

## 退出码

| 代码 | 含义 | 描述 |
|------|------|------|
| 0 | 成功 | 所有操作成功完成 |
| 1 | 运行时错误 | 依赖问题、自检失败 |
| 2 | 用法错误 | 无效命令行参数、缺少输入 |
| 3 | 数据错误 | 无效输入数据（格式错误的树、错误序列） |
| 130 | 中断 | 用户按 Ctrl+C（SIGINT）或收到 SIGTERM |

> 这些退出码由 `figtreekit/_cli.py` 中的 `ExitCode`（`IntEnum`）统一管理，数值与下表完全一致。

## 命令行用法

### 基本命令

```bash
figtreekit input.tre -o output.nex
figtreekit input.tre --validate
figtreekit --version    # 显示版本号、git hash 与构建日期
figtreekit --self-test
figtreekit --help
```

### 树样式

```bash
figtreekit input.tre -o out.nex --layout polar --tip-labels-show
figtreekit input.tre -o out.nex --branch-width 2.0 --background-color "#FFFFFF"
figtreekit input.tre -o out.nex --font-name Arial --font-size 12
figtreekit input.tre -o out.nex --node-labels-show --node-display-attribute height
```

### 分支折叠

```bash
figtreekit tree.nwk -o out.nex --clade Cyanobacteriota
figtreekit tree.nwk -o out.nex --clade Cyanobacteriota --strict
figtreekit tree.nwk -o out.nex --clade Cyanobacteriota --clade Proteobacteria
# 嵌套折叠：同时折叠内外分支
figtreekit tree.nwk -o out.nex --clade Phylum --clade Class
```

### 树根性设置

```bash
figtreekit tree.nwk -o out.nex --rooted      # 设置为有根树
figtreekit tree.nwk -o out.nex --unrooted    # 设置为无根树
```

### 多树处理

```bash
figtreekit multi.nex -o out.nex --multi-tree split
figtreekit multi.nex -o out.nex --multi-tree first
figtreekit multi.nex -o out.nex --multi-tree last
figtreekit multi.nex -o out.nex --multi-tree random
figtreekit multi.nex -o out.nex --multi-tree all    # 同 split
```

### 分类学配置

```bash
figtreekit tree.nwk -o out.nex --taxonomy-delimiter-mode greedy
figtreekit tree.nwk -o out.nex --taxonomy-table-sep "|"
figtreekit tree.nwk -o out.nex --taxonomy-source-priority table
figtreekit tree.nwk -o out.nex --taxonomy-levels "k:kingdom,ss:subspecies"
figtreekit tree.nwk -o out.nex --table-sep ","
figtreekit tree.nwk -o out.nex --taxonomy-mapping-file taxonomy.tsv
figtreekit tree.nwk -o out.nex --ignore-malformed
```

### 序列验证

```bash
figtreekit sequences.fasta --validate
figtreekit sequences.fasta --validate --mol-type DNA
figtreekit aligned.fasta --validate --skip-length-check
figtreekit tree.nwk -o out.nex --sequences sequences.fasta
figtreekit tree.nwk --validate --sequences sequences.fasta
```

> **注意**：对序列文件（FASTA/FASTQ）使用 `--validate` 时，深度验证通过后返回退出码 0（成功），即使该文件不是树格式。这允许在脚本中对序列文件进行独立的验证流程。

### 输出控制

```bash
figtreekit tree.nwk -o existing.nex --force
figtreekit tree.nwk -o existing.nex --no-clobber
figtreekit tree.nwk -o out.nex --log-file figtreekit.log
figtreekit tree.nwk -o out.nex --strip-annotations   # 移除括号注释以减小文件体积
```

### 渲染

FigTreeKit 使用基于 FigTree v1.4.4 修改的 JAR 进行无头渲染。安装包已内置打过补丁的 JAR，通常无需额外设置：

```bash
figtreekit input.tre -o out.nex --render tree.png
figtreekit input.tre -o out.nex --render tree.pdf --render-width 1600 --render-height 1000
figtreekit input.tre -o out.nex --render tree.svg
```

若从源码安装或需要重新编译 FigTree JAR，请确保已安装 Java 8+ 与 Apache Ant，然后运行：

```bash
figtreekit --setup-figtree                    # 下载源码、应用补丁并编译
figtreekit --setup-figtree --path /path/to/figtree.jar  # 使用已有的 JAR
```

`--setup-figtree` 会从 GitHub 下载 FigTree v1.4.4 官方源码，将 `_figtree_patch/src/figtree/` 中的单一补丁（`RadialTreeLayout.java`）写入源码树，再执行 `ant dist` 编译。手动编译步骤参见 `_figtree_patch/README.md`。

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

## Python API 用法

### 基本样式

```python
from figtreekit import FigTreeStyler, LayoutType, FontStyle

styler = FigTreeStyler("tree.nwk")
styler.set_layout(LayoutType.POLAR)
styler.set_appearance(background_color="#FFFFFF", branch_line_width=2.0)
styler.highlight_clade(["A", "B"], color="#FF0000")
styler.set_clade_color(["A", "B"], color="#2196F3")
styler.set_clade_color_all(["A", "B"], color="#2196F3")  # 子树全部分支着色
# 注意：set_clade_color + highlight_clade 作用于相同分类群时，
# MRCA 级别的颜色会被丢弃以避免 FigTree ClassCastException。
# 推荐使用 set_clade_color_all() 替代。
styler.set_clade_font(["A"], font_name="Arial", font_style=FontStyle.BOLD, font_size=14)
styler.set_tip_labels(is_shown=True, font_size=12)
styler.set_node_labels(is_shown=True, display_attribute="height")
styler.set_scale_bar(is_shown=True)
styler.export("output.nex")
styler.render("tree.png")
```

### 加载树

```python
# load_tree() 可自动检测文件路径或内联内容
styler = FigTreeStyler()
styler.load_tree("tree.nwk")  # 自动检测为文件路径
styler.load_tree("((A:0.1,B:0.2):0.3,C:0.4);")  # 自动检测为内联内容
```

### Clade 信息查询

```python
# 获取 clade 详细信息
info = styler.get_clade_info(["A", "B"])
# 返回包含 MRCA 节点、后代末端、分支长度等信息的字典
```

### 单系群与折叠

```python
# 按精确分类单元检查单系性
result = styler.check_monophyly(["A", "B", "C"])

# 按分类群名称检查（自动检测格式）
result = styler.check_monophyly_by_group("Cyanobacteriales")
result = styler.check_monophyly_by_group("LUCA")

# 折叠分支
styler.collapse_clade(["A", "B"], label="Clade1")
styler.collapse_by_group("Cyanobacteriales")
styler.collapse_by_group("Cyanobacteriales", label="Cyano")

# 嵌套折叠：同时折叠内外分支（自动按大小排序处理）
styler.collapse_clade(["A", "B"], label="Inner")
styler.collapse_clade(["A", "B", "C"], label="Outer")  # Inner 和 Outer 都会出现在输出中

# 移除树中所有括号注释（NHX、bootstrap、posterior 等），减小输出文件体积
styler.strip_annotations()
```

### 验证

```python
from figtreekit import validate_input_file, deep_validate_newick, deep_validate_fasta

# 文件验证
result = validate_input_file("tree.nwk")
if not result["valid"]:
    for err in result["errors"]:
        print(err)

# 深度 Newick 验证
dv = deep_validate_newick(content, label="tree.nwk")
for err in dv["errors"]:
    print(err)

# FASTA 验证
dv = deep_validate_fasta("seqs.fasta", expected_alphabet="DNA")
```

### 分类学

```python
from figtreekit import parse_taxonomy_auto, detect_taxonomy_format

# 自动检测并解析
tax = parse_taxonomy_auto("GB_GCA_000252485.1_d_Bacteria_p_Cyanobacteriota_c_...")
# {"domain": "Bacteria", "phylum": "Cyanobacteriota", ...}

tax = parse_taxonomy_auto("d__Archaea;p__Euryarchaeota;s__")
# {"domain": "Archaea", "phylum": "Euryarchaeota", "species": ""}

# 从 CLI 参数应用设置
from figtreekit import apply_cli_args
# apply_cli_args(styler, args)  # args 来自 argparse.Namespace

# 配置分类学解析行为
styler.configure_taxonomy(
    delimiter_mode="reverse",      # reverse / greedy / segment
    table_sep=";",                 # 格式 B 分隔符
    source_priority="table",       # table / embedded
    mapping_file="taxonomy.tsv",
    ignore_malformed=False,
)

# 分类学分析并自动识别单系群（需提供 pattern 或 mapping_file）
groups = styler.analyze_taxonomy(mapping_file="taxonomy.tsv", rank="phylum")
# 返回各门的单系群信息

# 从映射文件分析（等价便捷方法）
groups = styler.analyze_taxonomy_from_mapping("taxonomy.tsv", rank="phylum")

# 检查分类学数据完整性
completeness = styler.check_taxonomy_completeness(mapping_file="taxonomy.tsv")
```

### 库模式 API（Library Mode API）

以下标准化签名函数适用于第三方工作流（Snakemake/Nextflow）集成：

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

## 故障排除

### "File not found" 错误
确保输入路径存在且是常规文件（单文件模式不是目录）。

### "Multiple trees detected" 错误
使用 `--multi-tree` 指定处理策略：
- `--multi-tree first` — 仅处理第一棵树
- `--multi-tree split` — 处理所有树，输出带数字后缀
- `--multi-tree ask` — 打印摘要并退出（默认行为）

### "Non-monophyletic group" 警告
指定的 clade 不构成单系群。使用 `--strict` 终止，或跳过折叠。

### "Negative branch length" 严重错误
树包含负分支长度。处理前修复树。

### "Duplicate tip name" 错误
树包含重复的末端节点标签。确保所有末端名唯一。

### "Control character detected" 错误
节点名包含恶意字符（控制字符或 Unicode 双向文本覆盖）。清理输入文件。

### "Tree-sequence cross-validation FAILED" 错误
树末端标签与序列 ID 不匹配。使用 `--no-cross-check` 跳过，或修复标签使其一致。

### 大树性能
超过 10,000 个末端的树：
- 使用 `--low-memory` 模式
- 确保 FigTree 渲染有足够内存（>50k 末端需 2-4 GB）
- 安装 `psutil` 获取 DEBUG 级内存日志

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
