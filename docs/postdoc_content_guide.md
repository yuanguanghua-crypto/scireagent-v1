# 知识内容填写模板说明

## 文件位置
`docs/postdoc_content_template.csv`

## 总览

Excel 表格共 20 列：
- **前 7 列**：产品基本信息（已自动填充，不需要填写）
- **后 13 列**：需要你填写的知识内容

## 逐列说明

### 已自动填充（不需要填写）

| 列名 | 说明 |
|------|------|
| Catalog No | 产品编号，如 SC8047 |
| Product Name | 产品名称 |
| CAS | CAS 号 |
| Formula | 分子式 |
| MW | 分子量 |
| Purity | 纯度 |
| Storage | 存储条件 |

### 需要填写

| 列名 | 怎么填 | 示例 |
|------|--------|------|
| **Research Goal（研究方向）** | 这个产品属于哪个大的研究方向 | RNA Labeling / DNA Sequencing / Click Chemistry / Protein Engineering |
| **Application（实验场景）** | 具体用于什么实验 | RNA Fluorescent Labeling / Sanger Sequencing / CuAAC Bioconjugation |
| **Method（技术方法）** | 配合什么技术使用 | CuAAC Click Chemistry / NHS-Ester Conjugation / Enzymatic Incorporation |
| **Protocol Name（方案名称）** | 对应的实验方案名称 | CuAAC Azide-RNA Fluorescent Labeling Protocol |
| **Protocol Steps（方案步骤）** | 简要步骤（3-5 步即可） | 1. Prepare azide-RNA 2. Add click mix 3. Incubate 30min 4. Purify |
| **Protocol Materials（所需材料）** | 需要的试剂和设备 | CuSO4, THPTA, sodium ascorbate, alkyne-dye, gel filtration column |
| **Protocol Time（预计时间）** | 整个方案需要多长时间 | 2 hours / 3 hours / 1 day |
| **Protocol Difficulty（难度）** | 初级/中级/高级 | Beginner / Intermediate / Advanced |
| **Reference PMID（参考文献PMID）** | 支持这个产品用途的论文 PMID | 24151973, 25959142 |
| **Reference DOI（参考文献DOI）** | 论文 DOI（如果知道） | 10.1038/nprot.2014.001 |
| **Key Advantages（主要优势）** | 这个产品/方法的优势（2-3 条） | High specificity; Bioorthogonal; Fast reaction |
| **Key Limitations（主要局限）** | 这个产品/方法的局限（2-3 条） | Copper toxicity; Requires modified substrates |
| **Confidence（确定程度）** | 你对以上信息的确定程度 | 高 / 中 / 低 |

## 填写规则

1. **多个值用分号 `;` 分隔**
   - 示例：`RNA Fluorescent Labeling; RNA Biotin Labeling`

2. **同一类产品可以复制粘贴**
   - 比如所有 2'-Azido dNTP 系列（SC8044-8047）的 Research Goal、Application、Method 基本相同

3. **不确定的可以留空**
   - 特别是 Reference PMID，不知道可以不填

4. **Protocol Steps 写简要步骤即可**
   - 不需要像正式 Protocol 那么详细，3-5 步概括即可
   - 详细的 Protocol 内容后续可以单独补充

5. **可以新增 Research Goal / Application / Method**
   - 如果上面的选项不够用，直接写上新的名称即可

## 现有选项参考

### Research Goals（研究方向）
- RNA Analysis（RNA 分析）
- DNA Sequencing（DNA 测序）
- Click Chemistry（点击化学）
- Protein Engineering（蛋白质工程）
- **可以新增**

### Applications（实验场景）
- RNA Fluorescent Labeling（RNA 荧光标记）
- RNA Biotin Labeling（RNA 生物素标记）
- RNA Quantification（RNA 定量）
- Sanger Sequencing（Sanger 测序）
- NGS Library Preparation（NGS 文库构建）
- CuAAC Bioconjugation（CuAAC 生物偶联）
- Protein Fluorescent Labeling（蛋白荧光标记）
- **可以新增**

### Methods（技术方法）
- CuAAC Click Chemistry（铜催化点击化学）
- SPAAC Click Chemistry（无铜点击化学）
- NHS-Ester Conjugation（NHS 酯偶联）
- Enzymatic Incorporation（酶法掺入）
- BigDye Terminator Sequencing（BigDye 测序）
- Nextera DNA Library Prep（Nextera 文库构建）
- RiboGreen Quantification（RiboGreen 定量）
- Cy3/Cy5 Protein Labeling（Cy3/Cy5 蛋白标记）
- **可以新增**

## 填写完成后

把填好的 CSV 文件发给我，我会：
1. 导入数据库（创建实体 + 关联关系）
2. 用论文数据补充 Evidence
3. 生成完整的 FAQ 和 SEO 内容
4. 更新知识图谱
