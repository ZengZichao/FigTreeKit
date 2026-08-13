"""Generate comprehensive test files covering all FigTreeKit features.

Optimized to cover maximum features in minimum files.
Each file tests multiple related features simultaneously.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from figtreekit import FigTreeStyler, LayoutType, FontStyle

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
os.makedirs(OUTPUT_DIR, exist_ok=True)


def test_01_comprehensive_rectilinear():
    """综合测试：矩形布局 + 多种注解 + 标签 + 比例尺"""
    newick = "(((('Taxon 001':0.01,'Taxon 002':0.02):0.03,'Taxon 003':0.04):0.05,('Taxon 004':0.08,'Taxon 005':0.09):0.10):0.11,('Taxon 006':0.12,'Taxon 007':0.13):0.14);"
    styler = FigTreeStyler()
    styler.load_content(newick)
    
    # 布局
    styler.set_layout(LayoutType.RECTILINEAR)
    styler.set_rectilinear_layout(align_tip_labels=True, curvature=50)
    
    # 外观
    styler.set_appearance(
        background_color="#FAFAFA",
        foreground_color="#333333",
        selection_color="#FFEB3B",
        branch_line_width=2.0,
    )
    
    # 高亮注解 - 红色高亮第一组
    styler.highlight_clade(["Taxon 001", "Taxon 002", "Taxon 003"], color="#E91E63")
    # 颜色注解 - 蓝色标记第二组
    styler.set_clade_color(["Taxon 004", "Taxon 005"], color="#2196F3")
    # 颜色注解 - 绿色标记第三组
    styler.set_clade_color(["Taxon 006", "Taxon 007"], color="#4CAF50")
    # 字体注解 - 加粗第一个分类单元
    styler.set_clade_font(["Taxon 001"], "Arial", FontStyle.BOLD, 14)
    
    # 标签设置
    styler.set_tip_labels(is_shown=True, font_name="Arial", font_size=10)
    styler.set_node_labels(is_shown=True, font_name="Arial", font_size=8)
    styler.set_branch_labels(is_shown=True, font_size=8, color="#FF0000")
    
    # 比例尺
    styler.set_scale_bar(is_shown=True, font_size=8, color="#000000")
    styler.set_scale_axis(is_shown=True, major_ticks=0.05, show_grid=True)
    
    # 图例
    styler.set_legend(is_shown=True, position="topRight", font_size=10)
    
    # 高亮显示
    styler.set_hilighting(is_shown=True, gradient=True)
    
    styler.export(os.path.join(OUTPUT_DIR, "01_rectilinear_full.nex"))
    print("✓ 01_rectilinear_full.nex (矩形布局 + 高亮/颜色/字体注解 + 标签 + 比例尺 + 图例)")


def test_02_comprehensive_polar():
    """综合测试：极坐标布局 + 特殊字符taxa + 多重注解"""
    newick = "(('Taxon 001 (groupA)':0.01,'Taxon 002 [groupB]':0.02):0.03,('9606':0.04,'Taxon 003':0.05):0.06);"
    styler = FigTreeStyler()
    styler.load_content(newick)
    
    # 极坐标布局
    styler.set_layout(LayoutType.POLAR)
    styler.set_polar_layout(
        align_tip_labels=True,
        angular_range=270,
        root_angle=45,
        show_root=True,
    )
    
    # 外观
    styler.set_appearance(
        background_color="#1A1A2E",
        foreground_color="#EEEEEE",
        branch_line_width=1.5,
        branch_color_attribute="posterior",
        branch_color_gradient=True,
    )
    
    # 高亮注解
    styler.highlight_clade(["Taxon 001 (groupA)", "Taxon 002 [groupB]"], color="#FF6B6B", width=6)
    styler.set_clade_color(["9606", "Taxon 003"], color="#4ECDC4")
    
    # 标签
    styler.set_tip_labels(is_shown=True, font_name="Arial", font_size=9, color="#EEEEEE")
    
    styler.export(os.path.join(OUTPUT_DIR, "02_polar_special_chars.nex"))
    print("✓ 02_polar_special_chars.nex (极坐标 + 特殊字符taxa + 渐变颜色 + 暗色主题)")


def test_03_comprehensive_radial():
    """综合测试：辐射布局 + 节点形状 + 自定义参数"""
    newick = "((A:0.1,B:0.2):0.3,(C:0.4,(D:0.5,E:0.6):0.7):0.8);"
    styler = FigTreeStyler()
    styler.load_content(newick)
    
    # 辐射布局
    styler.set_layout(LayoutType.RADIAL)
    styler.set_radial_layout(spread=0.5, align_tip_labels=True)
    
    # 外观
    styler.set_appearance(
        background_color="#FFFFFF",
        foreground_color="#000000",
        branch_line_width=2.0,
    )
    
    # 注解
    styler.highlight_clade(["A", "B"], color="#FF9800")
    styler.highlight_clade(["D", "E"], color="#9C27B0")
    styler.set_clade_color(["C"], color="#607D8B")
    styler.set_clade_font(["A"], "Arial", FontStyle.BOLD, 12)
    styler.set_clade_stroke(["B"], stroke_width=3.0)
    
    # 节点形状和条形
    styler.set_node_shapes(is_shown=True, size=6, shape_type="circle")
    styler.set_node_bars(is_shown=True, bar_width=2.0)
    
    # 自定义参数
    styler.set_custom_param("appearance.branchMinLineWidth", 1.0)
    
    styler.export(os.path.join(OUTPUT_DIR, "03_radial_annotations.nex"))
    print("✓ 03_radial_annotations.nex (辐射布局 + 高亮/颜色/字体/描边 + 节点形状)")


def test_04_beast_like_numeric_taxa():
    """综合测试：BEAST风格数字taxa + translate block模拟 + 分支标签"""
    newick = "((9606:0.01,9598:0.02):0.03,(10090:0.04,10116:0.05):0.06);"
    styler = FigTreeStyler()
    styler.load_content(newick)
    
    styler.set_layout(LayoutType.RECTILINEAR)
    
    # 外观
    styler.set_appearance(
        background_color="#FFFFFF",
        foreground_color="#000000",
        branch_line_width=1.5,
        branch_color_attribute="posterior",
    )
    
    # 注解
    styler.highlight_clade(["9606", "9598"], color="#E3F2FD")
    styler.highlight_clade(["10090", "10116"], color="#FFF3E0")
    styler.set_clade_color(["9606"], color="#1565C0")
    styler.set_clade_color(["10090"], color="#E65100")
    
    # 分支标签 - 显示后验概率
    styler.set_branch_labels(
        is_shown=True,
        display_attribute="posterior",
        font_name="Arial",
        font_size=10,
        color="#D32F2F",
    )
    
    # 节点标签
    styler.set_node_labels(
        is_shown=True,
        display_attribute="height",
        font_name="Arial",
        font_size=8,
    )
    
    styler.export(os.path.join(OUTPUT_DIR, "04_beast_numeric_taxa.nex"))
    print("✓ 04_beast_numeric_taxa.nex (数字taxa + 分支/节点标签 + 颜色属性)")


def test_05_large_tree_with_multiple_clades():
    """综合测试：大树 + 多个clade注解 + 缩放设置"""
    # 生成30个taxa的完全二叉树
    taxa = [f"Species_{i:03d}" for i in range(30)]
    # Build strictly bifurcating tree
    nodes = [f"{t}:0.01" for t in taxa]
    import random
    r = random.Random(42)
    while len(nodes) > 1:
        r.shuffle(nodes)
        a, b = nodes[0], nodes[1]
        nodes = [f"({a},{b}):0.005"] + nodes[2:]
    newick = nodes[0] + ";"
    
    styler = FigTreeStyler()
    styler.load_content(newick)
    styler.set_layout(LayoutType.RECTILINEAR)
    
    # 外观
    styler.set_appearance(
        background_color="#F5F5F5",
        foreground_color="#212121",
        branch_line_width=1.0,
    )
    
    # 多个clade高亮
    styler.highlight_clade(taxa[0:5], color="#F44336")   # 红色组
    styler.highlight_clade(taxa[5:10], color="#2196F3")  # 蓝色组
    styler.highlight_clade(taxa[10:15], color="#4CAF50") # 绿色组
    styler.set_clade_color(taxa[15:20], color="#FF9800") # 橙色组
    styler.set_clade_color(taxa[20:25], color="#9C27B0") # 紫色组
    
    # 字体注解
    styler.set_clade_font([taxa[0]], "Arial", FontStyle.BOLD, 12)
    styler.set_clade_font([taxa[10]], "Courier", FontStyle.ITALIC, 10)
    
    # 缩放设置
    styler.set_scale(
        root_age=1.0,
        auto_scale=True,
    )
    
    # 标签
    styler.set_tip_labels(is_shown=True, font_name="Arial", font_size=9)
    
    styler.export(os.path.join(OUTPUT_DIR, "05_large_tree_multi_clade.nex"))
    print("✓ 05_large_tree_multi_clade.nex (30 taxa + 5个clade + 字体 + 缩放)")


def test_06_nexus_with_existing_settings():
    """综合测试：加载已有Nexus + 修改设置 + 保持原有figtree块"""
    nexus_content = """#NEXUS
begin taxa;
    dimensions ntax=5;
    taxlabels
        Alpha
        Beta
        Gamma
        Delta
        Epsilon
    ;
end;

begin trees;
    tree TREE1 = (((Alpha:0.1,Beta:0.2):0.3,Gamma:0.4):0.5,(Delta:0.6,Epsilon:0.7):0.8);
end;

begin figtree;
    set appearance.backgroundColour=#FFFFFF;
    set appearance.branchLineWidth=1.0;
    set layout.layoutType="RECTILINEAR";
    set tipLabels.isShown=true;
    set tipLabels.fontSize=12.0;
    set scaleBar.isShown=true;
end;
"""
    styler = FigTreeStyler()
    styler.load_content(nexus_content)
    
    # 添加新注解
    styler.highlight_clade(["Alpha", "Beta"], color="#E91E63")
    styler.highlight_clade(["Delta", "Epsilon"], color="#2196F3")
    styler.set_clade_color(["Gamma"], color="#4CAF50")
    styler.set_clade_font(["Alpha"], "Arial", FontStyle.BOLD, 14)
    
    # 修改外观
    styler.set_appearance(
        background_color="#FAFAFA",
        branch_line_width=2.0,
    )
    
    # 修改标签
    styler.set_tip_labels(font_size=10, font_name="Arial")
    
    styler.export(os.path.join(OUTPUT_DIR, "06_nexus_existing.nex"))
    print("✓ 06_nexus_existing.nex (加载已有Nexus + 添加注解 + 修改设置)")


def test_07_edge_cases():
    """综合测试：边界情况 - 深度嵌套树 + 零分支 + MRCA高亮"""
    newick = "((A:0.0,B:0.0):0.1,C:0.2);"
    styler = FigTreeStyler()
    styler.load_content(newick)
    styler.set_layout(LayoutType.RECTILINEAR)
    
    # 外观
    styler.set_appearance(
        background_color="#FFFFFF",
        foreground_color="#000000",
    )
    
    # MRCA方式高亮
    styler.set_clade_hilight("MRCA(A,B)", tip_count=2, height=0.0, color="#FFCDD2")
    
    # 标签
    styler.set_tip_labels(is_shown=True, font_size=12)
    styler.set_scale_bar(is_shown=True)
    
    styler.export(os.path.join(OUTPUT_DIR, "07_edge_cases.nex"))
    print("✓ 07_edge_cases.nex (深度嵌套 + 零分支 + MRCA高亮)")


def test_08_all_layouts_comparison():
    """综合测试：同一棵树的三种布局对比"""
    newick = "(((A:0.1,B:0.2):0.3,C:0.4):0.5,(D:0.6,(E:0.7,F:0.8):0.9):1.0);"
    
    for i, layout in enumerate([LayoutType.RECTILINEAR, LayoutType.POLAR, LayoutType.RADIAL], 1):
        styler = FigTreeStyler()
        styler.load_content(newick)
        styler.set_layout(layout)
        
        # 相同的注解
        styler.highlight_clade(["A", "B"], color="#F44336")
        styler.highlight_clade(["D", "E", "F"], color="#2196F3")
        styler.set_clade_color(["C"], color="#4CAF50")
        styler.set_clade_font(["A"], "Arial", FontStyle.BOLD, 12)
        
        # 相同的标签设置
        styler.set_tip_labels(is_shown=True, font_name="Arial", font_size=10)
        styler.set_node_labels(is_shown=True, font_size=8)
        styler.set_scale_bar(is_shown=True)
        
        # 布局特有设置
        if layout == LayoutType.POLAR:
            styler.set_polar_layout(align_tip_labels=True, angular_range=360)
        elif layout == LayoutType.RADIAL:
            styler.set_radial_layout(spread=0.5)
        elif layout == LayoutType.RECTILINEAR:
            styler.set_rectilinear_layout(align_tip_labels=True)
        
        styler.export(os.path.join(OUTPUT_DIR, f"08_layout_{layout.value.lower()}.nex"))
        print(f"✓ 08_layout_{layout.value.lower()}.nex ({layout.value}布局 + 相同注解对比)")


def test_09_method_chaining_and_reset():
    """综合测试：方法链 + reset复用 + 完整设置"""
    # 第一棵树 - 方法链
    newick1 = "((A:0.1,B:0.2):0.3,C:0.4);"
    (
        FigTreeStyler()
        .load_content(newick1)
        .set_layout(LayoutType.RECTILINEAR)
        .highlight_clade(["A", "B"], color="#E91E63")
        .set_clade_color(["C"], color="#2196F3")
        .set_tip_labels(is_shown=True, font_size=12)
        .set_scale_bar(is_shown=True)
        .set_appearance(background_color="#F5F5F5")
        .export(os.path.join(OUTPUT_DIR, "09a_chain_first.nex"))
    )
    print("✓ 09a_chain_first.nex (方法链示例)")
    
    # 第二棵树 - reset后复用
    styler = FigTreeStyler()
    styler.load_content(newick1)
    styler.highlight_clade(["A", "B"], color="#4CAF50")
    styler.export(os.path.join(OUTPUT_DIR, "09b_before_reset.nex"))
    
    styler.reset()
    newick2 = "((X:0.5,Y:0.6):0.7,Z:0.8);"
    styler.load_content(newick2)
    styler.set_layout(LayoutType.POLAR)
    styler.highlight_clade(["X", "Y"], color="#FF9800")
    styler.set_tip_labels(is_shown=True)
    styler.export(os.path.join(OUTPUT_DIR, "09c_after_reset.nex"))
    print("✓ 09b_before_reset.nex + 09c_after_reset.nex (reset复用)")


def test_10_custom_params_and_no_taxa():
    """综合测试：自定义参数 + 无taxa块导出 + 离散颜色"""
    newick = "((A:0.1,B:0.2):0.3,(C:0.4,D:0.5):0.6);"
    styler = FigTreeStyler()
    styler.load_content(newick)
    styler.set_layout(LayoutType.RECTILINEAR)
    
    # 外观 - 离散颜色
    styler.set_appearance(
        branch_color_attribute="species",
        discrete_coloring=True,
        branch_line_width=1.5,
    )
    
    # 注解
    styler.highlight_clade(["A", "B"], color="#FFCDD2")
    styler.set_clade_color(["C", "D"], color="#C8E6C9")
    
    # 自定义参数
    styler.set_custom_param("custom.myParam", "testValue")
    styler.set_custom_param("appearance.branchMinLineWidth", 0.5)
    
    # 标签
    styler.set_tip_labels(is_shown=True)
    
    # 无taxa块导出
    styler.export(os.path.join(OUTPUT_DIR, "10_custom_no_taxa.nex"), include_taxa_block=False)
    print("✓ 10_custom_no_taxa.nex (自定义参数 + 离散颜色 + 无taxa块)")


def main():
    print("=" * 70)
    print("FigTreeKit 综合功能测试 - 10个文件覆盖全部功能")
    print("=" * 70)
    print()
    
    test_01_comprehensive_rectilinear()
    test_02_comprehensive_polar()
    test_03_comprehensive_radial()
    test_04_beast_like_numeric_taxa()
    test_05_large_tree_with_multiple_clades()
    test_06_nexus_with_existing_settings()
    test_07_edge_cases()
    test_08_all_layouts_comparison()
    test_09_method_chaining_and_reset()
    test_10_custom_params_and_no_taxa()
    
    print()
    print("=" * 70)
    print(f"所有文件已生成至: {OUTPUT_DIR}")
    print("=" * 70)
    print()
    print("功能覆盖矩阵:")
    print("-" * 70)
    print(f"{'功能':<30} {'测试文件':<40}")
    print("-" * 70)
    print(f"{'矩形布局':<30} {'01, 04, 05, 06, 07, 09, 10':<40}")
    print(f"{'极坐标布局':<30} {'02, 08':<40}")
    print(f"{'辐射布局':<30} {'03, 08':<40}")
    print(f"{'高亮注解':<30} {'01, 02, 03, 04, 05, 06, 07, 08, 09, 10':<40}")
    print(f"{'颜色注解':<30} {'01, 03, 04, 05, 06, 08, 09, 10':<40}")
    print(f"{'字体注解':<30} {'01, 03, 05, 06, 08':<40}")
    print(f"{'描边注解':<30} {'03':<40}")
    print(f"{'MRCA高亮':<30} {'07':<40}")
    print(f"{'分支标签':<30} {'01, 04':<40}")
    print(f"{'节点标签':<30} {'01, 04, 08':<40}")
    print(f"{'Tip标签':<30} {'01, 02, 03, 04, 05, 06, 07, 08, 09, 10':<40}")
    print(f"{'比例尺':<30} {'01, 07, 08, 09':<40}")
    print(f"{'坐标轴':<30} {'01':<40}")
    print(f"{'图例':<30} {'01':<40}")
    print(f"{'节点形状':<30} {'03':<40}")
    print(f"{'节点条':<30} {'03':<40}")
    print(f"{'颜色渐变':<30} {'02':<40}")
    print(f"{'离散颜色':<30} {'10':<40}")
    print(f"{'数字taxa':<30} {'04':<40}")
    print(f"{'特殊字符taxa':<30} {'02':<40}")
    print(f"{'大树(30taxa)':<30} {'05':<40}")
    print(f"{'三叉树':<30} {'07':<40}")
    print(f"{'已有Nexus':<30} {'06':<40}")
    print(f"{'方法链':<30} {'09':<40}")
    print(f"{'Reset复用':<30} {'09':<40}")
    print(f"{'自定义参数':<30} {'10':<40}")
    print(f"{'无taxa块导出':<30} {'10':<40}")
    print(f"{'缩放设置':<30} {'05':<40}")
    print(f"{'深色主题':<30} {'02':<40}")
    print("-" * 70)


if __name__ == "__main__":
    main()
